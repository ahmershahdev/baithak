from typing import cast

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
from apps.chat.throttles import SendThrottle
from apps.core import channels as rules
from apps.workspaces import audit

PAGE_SIZE = 50
CATCH_UP_LIMIT = 500
MAX_BODY = 4000


class AuthorSerializer(serializers.Serializer[User]):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)


class MessageSerializer(serializers.ModelSerializer[Message]):
    author = AuthorSerializer(read_only=True, allow_null=True)
    deleted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Message
        fields = (
            "id",
            "seq",
            "event",
            "author",
            "body",
            "client_id",
            "created_at",
            "edited_at",
            "deleted",
        )
        read_only_fields = fields


class MessagePageSerializer(serializers.Serializer[None]):
    messages = MessageSerializer(many=True)
    has_more = serializers.BooleanField()
    last_seq = serializers.IntegerField()
    last_event = serializers.IntegerField()


class BodySerializer(serializers.Serializer[None]):
    body = serializers.CharField(max_length=MAX_BODY, trim_whitespace=True)


class SendSerializer(BodySerializer):
    client_id = serializers.RegexField(r"^[A-Za-z0-9_-]{1,64}$", required=False, allow_blank=True)


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
        found = Message.objects.filter(channel=access.channel).select_related("author")
        after_event = _int_param(request, "after_event")
        if after_event is not None:
            changed = list(
                found.filter(event__gt=after_event).order_by("event")[: CATCH_UP_LIMIT + 1]
            )
            return _page(access, changed[:CATCH_UP_LIMIT], len(changed) > CATCH_UP_LIMIT)
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
        allowed = rules.can_post(
            access.role, access.kind, is_member=access.is_member, archived=access.channel.archived
        )
        if not allowed:
            raise PermissionDenied(
                "This channel is archived."
                if access.channel.archived
                else "Join the channel to post in it."
            )
        serializer = SendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message, created = messages.post(
            access.channel,
            user,
            serializer.validated_data["body"],
            serializer.validated_data.get("client_id", ""),
        )
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MessageDetailView(APIView):
    def _message(self, access: ChannelAccess, seq: int) -> Message:
        message = (
            Message.objects.filter(channel=access.channel, seq=seq)
            .select_related("author", "channel")
            .first()
        )
        if message is None:
            raise Http404
        return message

    @extend_schema(
        request=BodySerializer,
        responses={200: MessageSerializer, 403: DetailSerializer},
        summary="Edit your message",
    )
    def patch(self, request: Request, slug: str, channel_id: int, seq: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        message = self._message(access, seq)
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

    @extend_schema(responses={204: None, 403: DetailSerializer}, summary="Delete a message")
    def delete(self, request: Request, slug: str, channel_id: int, seq: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        message = self._message(access, seq)
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
                audit.record(
                    access.member.workspace,
                    user,
                    "message.delete",
                    message,
                    {"channel": access.channel.name, "seq": message.seq},
                )
        return Response(status=status.HTTP_204_NO_CONTENT)
