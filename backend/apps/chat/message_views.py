from typing import Any, cast

from django.db import transaction
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import DetailSerializer
from apps.chat import messages
from apps.chat.access import ChannelAccess, channel_access
from apps.chat.models import Message
from apps.chat.serializers import MESSAGE_PREFETCH, MessageSerializer
from apps.chat.throttles import SendThrottle
from apps.core import channels as rules
from apps.core import reactions as reaction_rules
from apps.core.reactions import MAX_DISTINCT
from apps.workspaces import audit

PAGE_SIZE = 50
MAX_ATTACHMENTS = 10
FILES_UNAVAILABLE = "Those files can't be sent: upload them to this channel again."
THREAD_PAGE_SIZE = 100
CATCH_UP_LIMIT = 500
MAX_BODY = 4000


class MessagePageSerializer(serializers.Serializer[None]):
    messages = MessageSerializer(many=True)
    has_more = serializers.BooleanField()
    last_seq = serializers.IntegerField()
    last_event = serializers.IntegerField()


class BodySerializer(serializers.Serializer[None]):
    body = serializers.CharField(max_length=MAX_BODY, trim_whitespace=True)


class SendSerializer(serializers.Serializer[None]):
    body = serializers.CharField(
        max_length=MAX_BODY, trim_whitespace=True, required=False, allow_blank=True, default=""
    )
    client_id = serializers.RegexField(r"^[A-Za-z0-9_-]{1,64}$", required=False, allow_blank=True)
    attachments = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        max_length=MAX_ATTACHMENTS,
        help_text="Ids of files you uploaded to this channel and haven't sent yet.",
    )

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data["body"] and not data["attachments"]:
            raise serializers.ValidationError({"body": ["Write a message or attach a file."]})
        return data


class ReplySerializer(SendSerializer):
    also_in_channel = serializers.BooleanField(default=False)


class ThreadPageSerializer(serializers.Serializer[None]):
    parent = MessageSerializer()
    replies = MessageSerializer(many=True)
    has_more = serializers.BooleanField()


def _user(request: Request) -> User:
    return cast(User, request.user)


def _page(access: ChannelAccess, found: list[Message], has_more: bool) -> Response:
    return Response(
        {
            "messages": MessageSerializer(found, many=True).data,
            "has_more": has_more,
            "last_seq": access.channel.last_seq,
            "last_event": access.channel.last_event,
        }
    )


def _int_param(request: Request, name: str) -> int | None:
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError as error:
        raise serializers.ValidationError({name: ["Expected a whole number."]}) from error
    if value < 0:
        raise serializers.ValidationError({name: ["Expected zero or more."]})
    return value


def _check_can_post(access: ChannelAccess) -> None:
    allowed = rules.can_post(
        access.role, access.kind, is_member=access.is_member, archived=access.channel.archived
    )
    if not allowed:
        raise PermissionDenied(
            "This channel is archived."
            if access.channel.archived
            else "Join the channel to post in it."
        )


def _channel_message(access: ChannelAccess, seq: int) -> Message:
    message = (
        Message.objects.filter(channel=access.channel, seq=seq)
        .select_related("author", "channel", "parent")
        .first()
    )
    if message is None:
        raise Http404
    return message


class MessageListView(APIView):
    throttle_classes = (SendThrottle,)
    throttle_scope = "post"

    @extend_schema(
        parameters=[
            OpenApiParameter("before", int, description="Older messages: seq below this."),
            OpenApiParameter(
                "after_event",
                int,
                description="Catch up: everything changed after this event, oldest first.",
            ),
        ],
        responses={200: MessagePageSerializer},
        summary="Message history, or catch-up after a reconnect",
    )
    def get(self, request: Request, slug: str, channel_id: int) -> Response:
        access = channel_access(_user(request), slug, channel_id)
        found = (
            Message.objects.filter(channel=access.channel)
            .select_related("author", "parent")
            .prefetch_related(*MESSAGE_PREFETCH)
        )
        after_event = _int_param(request, "after_event")
        if after_event is not None:
            changed = list(
                found.filter(event__gt=after_event).order_by("event")[: CATCH_UP_LIMIT + 1]
            )
            return _page(access, changed[:CATCH_UP_LIMIT], len(changed) > CATCH_UP_LIMIT)
        found = found.filter(seq__isnull=False)
        before = _int_param(request, "before")
        if before is not None:
            found = found.filter(seq__lt=before)
        newest = list(found.order_by("-seq")[: PAGE_SIZE + 1])
        page = list(reversed(newest[:PAGE_SIZE]))
        return _page(access, page, len(newest) > PAGE_SIZE)

    @extend_schema(
        request=SendSerializer,
        responses={201: MessageSerializer, 200: MessageSerializer, 403: DetailSerializer},
        summary="Send a message",
    )
    def post(self, request: Request, slug: str, channel_id: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        _check_can_post(access)
        serializer = SendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message, created = messages.post(
                access.channel,
                user,
                serializer.validated_data["body"],
                serializer.validated_data.get("client_id", ""),
                attachment_ids=serializer.validated_data["attachments"],
            )
        except messages.FilesUnavailable as error:
            raise serializers.ValidationError({"attachments": [FILES_UNAVAILABLE]}) from error
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class _EditDeleteView(APIView):
    """Edit and delete, for a message found by `_message`."""

    def _message(self, access: ChannelAccess, **kwargs: int) -> Message:
        raise NotImplementedError

    def _edit(self, request: Request, slug: str, channel_id: int, **kwargs: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        message = self._message(access, **kwargs)
        allowed = rules.can_edit_message(
            is_author=message.author_id == user.pk,
            deleted=message.deleted,
            archived=access.channel.archived,
        )
        if not allowed:
            raise PermissionDenied("You can only edit your own messages.")
        serializer = BodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["body"] != message.body:
            messages.edit(message, serializer.validated_data["body"])
        return Response(MessageSerializer(message).data)

    def _delete(self, request: Request, slug: str, channel_id: int, **kwargs: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        message = self._message(access, **kwargs)
        allowed = rules.can_delete_message(
            access.role, is_author=message.author_id == user.pk, deleted=message.deleted
        )
        if not allowed:
            raise PermissionDenied("You can only delete your own messages.")
        with transaction.atomic():
            messages.delete(message)
            # Removing someone else's words is moderation, so it is audited; authors deleting
            # their own messages are not.
            if message.author_id != user.pk:
                where: dict[str, object] = {"channel": access.channel.name, "seq": message.seq}
                if message.parent is not None:
                    where = {
                        "channel": access.channel.name,
                        "thread": message.parent.seq,
                        "reply": message.thread_seq,
                    }
                audit.record(access.member.workspace, user, "message.delete", message, where)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageDetailView(_EditDeleteView):
    def _message(self, access: ChannelAccess, **kwargs: int) -> Message:
        return _channel_message(access, kwargs["seq"])

    @extend_schema(
        request=BodySerializer,
        responses={200: MessageSerializer, 403: DetailSerializer},
        summary="Edit your message",
    )
    def patch(self, request: Request, slug: str, channel_id: int, seq: int) -> Response:
        return self._edit(request, slug, channel_id, seq=seq)

    @extend_schema(responses={204: None, 403: DetailSerializer}, summary="Delete a message")
    def delete(self, request: Request, slug: str, channel_id: int, seq: int) -> Response:
        return self._delete(request, slug, channel_id, seq=seq)


def _thread_parent(access: ChannelAccess, seq: int) -> Message:
    parent = _channel_message(access, seq)
    # One level of threads: a reply also sent to the channel has a seq but takes no replies.
    if parent.parent_id is not None:
        raise Http404
    return parent


class ThreadView(APIView):
    throttle_classes = (SendThrottle,)
    throttle_scope = "post"

    @extend_schema(
        parameters=[OpenApiParameter("after", int, description="Replies after this thread_seq.")],
        responses={200: ThreadPageSerializer},
        summary="A thread: its first message and replies, oldest first",
    )
    def get(self, request: Request, slug: str, channel_id: int, seq: int) -> Response:
        access = channel_access(_user(request), slug, channel_id)
        parent = _thread_parent(access, seq)
        found = (
            Message.objects.filter(parent=parent)
            .select_related("author", "parent")
            .prefetch_related(*MESSAGE_PREFETCH)
        )
        after = _int_param(request, "after")
        if after is not None:
            found = found.filter(thread_seq__gt=after)
        replies = list(found.order_by("thread_seq")[: THREAD_PAGE_SIZE + 1])
        return Response(
            {
                "parent": MessageSerializer(parent).data,
                "replies": MessageSerializer(replies[:THREAD_PAGE_SIZE], many=True).data,
                "has_more": len(replies) > THREAD_PAGE_SIZE,
            }
        )

    @extend_schema(
        request=ReplySerializer,
        responses={201: MessageSerializer, 200: MessageSerializer, 403: DetailSerializer},
        summary="Reply in a thread",
    )
    def post(self, request: Request, slug: str, channel_id: int, seq: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        _check_can_post(access)
        parent = _thread_parent(access, seq)
        serializer = ReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message, created = messages.post(
                access.channel,
                user,
                serializer.validated_data["body"],
                serializer.validated_data.get("client_id", ""),
                parent=parent,
                also_in_channel=serializer.validated_data["also_in_channel"],
                attachment_ids=serializer.validated_data["attachments"],
            )
        except messages.FilesUnavailable as error:
            raise serializers.ValidationError({"attachments": [FILES_UNAVAILABLE]}) from error
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


def _reply(access: ChannelAccess, seq: int, thread_seq: int) -> Message:
    parent = _thread_parent(access, seq)
    reply = (
        Message.objects.filter(parent=parent, thread_seq=thread_seq)
        .select_related("author", "channel", "parent")
        .first()
    )
    if reply is None:
        raise Http404
    return reply


class ReplyDetailView(_EditDeleteView):
    def _message(self, access: ChannelAccess, **kwargs: int) -> Message:
        return _reply(access, kwargs["seq"], kwargs["thread_seq"])

    @extend_schema(
        request=BodySerializer,
        responses={200: MessageSerializer, 403: DetailSerializer},
        summary="Edit your reply",
    )
    def patch(
        self, request: Request, slug: str, channel_id: int, seq: int, thread_seq: int
    ) -> Response:
        return self._edit(request, slug, channel_id, seq=seq, thread_seq=thread_seq)

    @extend_schema(responses={204: None, 403: DetailSerializer}, summary="Delete a reply")
    def delete(
        self, request: Request, slug: str, channel_id: int, seq: int, thread_seq: int
    ) -> Response:
        return self._delete(request, slug, channel_id, seq=seq, thread_seq=thread_seq)


class EmojiSerializer(serializers.Serializer[None]):
    emoji = serializers.CharField(max_length=32)

    def validate_emoji(self, value: str) -> str:
        if not reaction_rules.is_emoji(value):
            raise serializers.ValidationError("Use one emoji.")
        return value


def _reaction_target(access: ChannelAccess, seq: int, thread_seq: int | None) -> Message:
    return _channel_message(access, seq) if thread_seq is None else _reply(access, seq, thread_seq)


def _react(
    request: Request,
    slug: str,
    channel_id: int,
    seq: int,
    thread_seq: int | None,
    emoji: str,
    on: bool,
) -> Response:
    user = _user(request)
    access = channel_access(user, slug, channel_id)
    message = _reaction_target(access, seq, thread_seq)
    allowed = reaction_rules.can_react(
        access.role,
        access.kind,
        is_member=access.is_member,
        archived=access.channel.archived,
        deleted=message.deleted,
    )
    if not allowed:
        raise PermissionDenied("Join the channel to react, and only to messages still there.")
    try:
        messages.react(message, user, emoji, on=on)
    except messages.TooManyReactions as error:
        raise serializers.ValidationError(
            {"emoji": [f"A message can have up to {MAX_DISTINCT} different reactions."]}
        ) from error
    fresh = (
        Message.objects.filter(pk=message.pk)
        .select_related("author", "parent")
        .prefetch_related(*MESSAGE_PREFETCH)
        .get()
    )
    return Response(MessageSerializer(fresh).data)


class ReactionsView(APIView):
    @extend_schema(
        request=EmojiSerializer,
        responses={200: MessageSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="React to a message or reply with an emoji",
    )
    def post(
        self, request: Request, slug: str, channel_id: int, seq: int, thread_seq: int | None = None
    ) -> Response:
        serializer = EmojiSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emoji = serializer.validated_data["emoji"]
        return _react(request, slug, channel_id, seq, thread_seq, emoji, on=True)


class ReactionView(APIView):
    @extend_schema(
        responses={200: MessageSerializer, 403: DetailSerializer},
        summary="Take back your reaction",
    )
    def delete(
        self,
        request: Request,
        slug: str,
        channel_id: int,
        seq: int,
        emoji: str,
        thread_seq: int | None = None,
    ) -> Response:
        return _react(request, slug, channel_id, seq, thread_seq, emoji, on=False)
