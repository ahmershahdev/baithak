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
from apps.chat.access import channel_access, readable_channels
from apps.chat.models import Channel, ChannelMember
from apps.chat.serializers import (
    AddChannelMemberSerializer,
    ChannelCreateSerializer,
    ChannelMemberSerializer,
    ChannelSerializer,
    ChannelUpdateSerializer,
)
from apps.core import channels as rules
from apps.core.roles import Role
from apps.workspaces import audit
from apps.workspaces.access import membership
from apps.workspaces.models import Member

NAME_TAKEN = "A channel with this name already exists."


def _user(request: Request) -> User:
    return cast(User, request.user)


def _serialize(channel: Channel, *, is_member: bool) -> dict[str, object]:
    channel.is_member = is_member  # type: ignore[attr-defined]
    return dict(ChannelSerializer(channel).data)


class ChannelListView(APIView):
    @extend_schema(responses={200: ChannelSerializer(many=True)}, summary="Channels I can see")
    def get(self, request: Request, slug: str) -> Response:
        member = membership(_user(request), slug)
        channels = readable_channels(member).order_by("name")
        return Response(ChannelSerializer(channels, many=True).data)

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
        return Response(_serialize(channel, is_member=True), status=status.HTTP_201_CREATED)


class ChannelDetailView(APIView):
    @extend_schema(responses={200: ChannelSerializer}, summary="One channel")
    def get(self, request: Request, slug: str, channel_id: int) -> Response:
        access = channel_access(_user(request), slug, channel_id)
        return Response(_serialize(access.channel, is_member=access.is_member))

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
        except IntegrityError as error:
            raise ValidationError({"name": [NAME_TAKEN]}) from error
        return Response(_serialize(channel, is_member=access.is_member))


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
                ChannelMember.objects.get_or_create(channel=channel, user=user)
                audit.record(
                    access.member.workspace, user, "channel.join", channel, {"name": channel.name}
                )
        return Response(_serialize(channel, is_member=True))


class ChannelLeaveView(APIView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request, slug: str, channel_id: int) -> Response:
        user = _user(request)
        access = channel_access(user, slug, channel_id)
        if access.is_member:
            with transaction.atomic():
                ChannelMember.objects.filter(channel=access.channel, user=user).delete()
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
        if not rules.can_add_member(access.role, is_member=access.is_member):
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
        with transaction.atomic():
            added, created = ChannelMember.objects.get_or_create(
                channel=access.channel, user=target.user
            )
            if created:
                audit.record(
                    workspace,
                    user,
                    "channel.add_member",
                    access.channel,
                    {"user": target.user.username},
                )
        return Response(
            ChannelMemberSerializer(added).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
