from typing import cast

from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import DetailSerializer
from apps.chat import events
from apps.chat.access import channel_access, readable_channels
from apps.chat.models import Channel, ChannelMember
from apps.chat.reads import mark_read, unread_of, with_read_state
from apps.chat.serializers import (
    PEOPLE_PREFETCH,
    AddChannelMemberSerializer,
    ChannelCreateSerializer,
    ChannelMemberSerializer,
    ChannelSerializer,
    ChannelUpdateSerializer,
    ConversationSerializer,
    ReadMarkerSerializer,
    ReadSerializer,
)
from apps.core import channels as rules
from apps.core import conversations
from apps.core.roles import Role
from apps.workspaces import audit
from apps.workspaces.access import membership
from apps.workspaces.models import Member

NAME_TAKEN = "A channel with this name already exists."
GUESTS_DM_ONLY = "Guests can only use direct messages. Make them a member to add them."


def _user(request: Request) -> User:
    return cast(User, request.user)


def _with_state(channel: Channel) -> Channel:
    last_read = getattr(channel, "last_read_seq", None)
    channel.is_member = last_read is not None  # type: ignore[attr-defined]
    channel.unread = unread_of(channel)  # type: ignore[attr-defined]
    return channel


def _serialize(channel: Channel, user: User) -> dict[str, object]:
    fresh = (
        with_read_state(Channel.objects.filter(pk=channel.pk), user.pk)
        .prefetch_related(PEOPLE_PREFETCH)
        .get()
    )
    return dict(ChannelSerializer(_with_state(fresh)).data)


class ChannelListView(APIView):
    @extend_schema(responses={200: ChannelSerializer(many=True)}, summary="Channels I can see")
    def get(self, request: Request, slug: str) -> Response:
        user = _user(request)
        member = membership(user, slug)
        channels = (
            with_read_state(readable_channels(member), user.pk)
            .prefetch_related(PEOPLE_PREFETCH)
            .order_by("name")
        )
        return Response(ChannelSerializer([_with_state(c) for c in channels], many=True).data)

    @extend_schema(
        request=ChannelCreateSerializer,
        responses={201: ChannelSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Create a channel",
    )
    def post(self, request: Request, slug: str) -> Response:
        user = _user(request)
        member = membership(user, slug)
        if not rules.can_create(Role(member.role)):
            raise PermissionDenied("Guests can't create channels.")
        serializer = ChannelCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        workspace = member.workspace
        try:
            with transaction.atomic():
                channel = Channel.objects.create(
                    workspace=workspace,
                    name=data["name"],
                    kind=data["kind"],
                    topic=data.get("topic", ""),
                    created_by=user,
                )
                ChannelMember.objects.create(channel=channel, user=user)
                audit.record(
                    workspace,
                    user,
                    "channel.create",
                    channel,
                    {"name": channel.name, "kind": channel.kind},
                )
        except IntegrityError as error:
            raise ValidationError({"name": [NAME_TAKEN]}) from error
        return Response(_serialize(channel, user), status=status.HTTP_201_CREATED)


class ChannelDetailView(APIView):
    @extend_schema(responses={200: ChannelSerializer}, summary="One channel")
    def get(self, request: Request, slug: str, channel_id: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        return Response(_serialize(access.channel, user))

    @extend_schema(
        request=ChannelUpdateSerializer,
        responses={200: ChannelSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Rename, change the topic, archive or unarchive",
    )
    def patch(self, request: Request, slug: str, channel_id: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        channel = access.channel
        allowed = rules.can_manage(
            access.role,
            access.kind,
            is_creator=channel.created_by_id == user.pk,
            is_member=access.is_member,
        )
        if not allowed:
            raise PermissionDenied("Only admins and the person who made it can change a channel.")
        serializer = ChannelUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if channel.is_default and data.get("archived"):
            raise PermissionDenied("The default channel can't be archived.")
        before = {"name": channel.name, "topic": channel.topic, "archived": channel.archived}
        if "name" in data:
            channel.name = data["name"]
        if "topic" in data:
            channel.topic = data["topic"]
        if "archived" in data and data["archived"] != channel.archived:
            channel.archived_at = timezone.now() if data["archived"] else None
        after = {"name": channel.name, "topic": channel.topic, "archived": channel.archived}
        changes = audit.diff(before, after)
        try:
            with transaction.atomic():
                channel.save(update_fields=["name", "topic", "archived_at"])
                if changes:
                    audit.record(access.member.workspace, user, "channel.update", channel, changes)
                    events.channel_changed(channel)
        except IntegrityError as error:
            raise ValidationError({"name": [NAME_TAKEN]}) from error
        return Response(_serialize(channel, user))


class ChannelJoinView(APIView):
    @extend_schema(request=None, responses={200: ChannelSerializer, 403: DetailSerializer})
    def post(self, request: Request, slug: str, channel_id: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        channel = access.channel
        if not access.is_member:
            if not rules.can_join(access.role, access.kind, archived=channel.archived):
                raise PermissionDenied("You can't join this channel.")
            with transaction.atomic():
                ChannelMember.objects.get_or_create(
                    channel=channel, user=user, defaults={"last_read_seq": channel.last_seq}
                )
                audit.record(
                    access.member.workspace, user, "channel.join", channel, {"name": channel.name}
                )
                events.access_changed(user.pk)
        return Response(_serialize(channel, user))


class ChannelLeaveView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request, slug: str, channel_id: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        if access.is_member:
            with transaction.atomic():
                ChannelMember.objects.filter(channel=access.channel, user=user).delete()
                events.access_changed(user.pk)
                audit.record(
                    access.member.workspace,
                    user,
                    "channel.leave",
                    access.channel,
                    {"name": access.channel.name},
                )
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChannelMembersView(APIView):
    @extend_schema(responses={200: ChannelMemberSerializer(many=True)}, summary="Who is in it")
    def get(self, request: Request, slug: str, channel_id: int) -> Response:
        access = channel_access(_user(request), slug, channel_id)
        members = (
            ChannelMember.objects.filter(channel=access.channel)
            .select_related("user")
            .order_by("user__username")
        )
        return Response(ChannelMemberSerializer(members, many=True).data)

    @extend_schema(
        request=AddChannelMemberSerializer,
        responses={201: ChannelMemberSerializer, 403: DetailSerializer, 404: DetailSerializer},
        summary="Add a workspace member to the channel",
    )
    def post(self, request: Request, slug: str, channel_id: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        if not rules.can_add_member(access.role, access.kind, is_member=access.is_member):
            raise PermissionDenied("Only people in the channel can add others.")
        if access.channel.archived:
            raise PermissionDenied("This channel is archived.")
        serializer = AddChannelMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = access.member.workspace
        target = (
            Member.objects.for_workspace(workspace)
            .select_related("user")
            .filter(user_id=serializer.validated_data["user_id"])
            .first()
        )
        if target is None:
            return Response(
                {"detail": "That person is not in this workspace."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not rules.can_be_in(Role(target.role), access.kind):
            raise ValidationError({"user_id": [GUESTS_DM_ONLY]})
        with transaction.atomic():
            added, created = ChannelMember.objects.get_or_create(
                channel=access.channel,
                user=target.user,
                defaults={"last_read_seq": access.channel.last_seq},
            )
            if created:
                audit.record(
                    workspace,
                    user,
                    "channel.add_member",
                    access.channel,
                    {"user": target.user.username},
                )
                events.access_changed(target.user_id)
        return Response(
            ChannelMemberSerializer(added).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ChannelReadView(APIView):
    @extend_schema(
        request=ReadSerializer,
        responses={200: ReadMarkerSerializer, 403: DetailSerializer},
        summary="Mark the channel read up to a seq",
    )
    def post(self, request: Request, slug: str, channel_id: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        serializer = ReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        marker = mark_read(access.channel, user.pk, serializer.validated_data["seq"])
        if marker is None:
            raise PermissionDenied("Join the channel to keep your place in it.")
        channel = with_read_state(Channel.objects.filter(pk=access.channel.pk), user.pk).get()
        return Response(
            {"channel": channel.pk, "last_read_seq": marker, "unread": unread_of(channel)}
        )


class ConversationView(APIView):
    @extend_schema(
        request=ConversationSerializer,
        responses={200: ChannelSerializer, 201: ChannelSerializer, 400: DetailSerializer},
        summary="Open a direct or group conversation, starting it if it doesn't exist",
    )
    def post(self, request: Request, slug: str) -> Response:
        user = _user(request)
        member = membership(user, slug)
        serializer = ConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        people = set(serializer.validated_data["user_ids"]) | {user.pk}
        kind = conversations.kind_for(len(people))
        if kind is None:
            others = conversations.MAX_PEOPLE - 1
            raise ValidationError({"user_ids": [f"Pick 1 to {others} other people."]})
        workspace = member.workspace
        if Member.objects.for_workspace(workspace).filter(user_id__in=people).count() != len(
            people
        ):
            raise ValidationError({"user_ids": ["Everyone must be in this workspace."]})
        with transaction.atomic():
            channel, created = Channel.objects.get_or_create(
                workspace=workspace,
                name=conversations.key(people),
                defaults={"kind": kind, "created_by": user},
            )
            # Opening it again brings back anyone who left.
            for person in people:
                _, joined = ChannelMember.objects.get_or_create(
                    channel=channel, user_id=person, defaults={"last_read_seq": channel.last_seq}
                )
                if joined:
                    events.access_changed(person)
            if created:
                # Who talks to whom stays out of the log: only the kind and the size.
                audit.record(
                    workspace,
                    user,
                    "conversation.create",
                    channel,
                    {"kind": kind.value, "people": len(people)},
                )
        return Response(
            _serialize(channel, user),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
