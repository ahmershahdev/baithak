from typing import cast

from django.db import transaction
from django.db.models import QuerySet, prefetch_related_objects
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.chat import events
from apps.chat.access import readable_channels
from apps.chat.serializers import MESSAGE_PREFETCH
from apps.notifications.models import Notification
from apps.notifications.serializers import (
    MarkReadSerializer,
    NotificationPageSerializer,
    NotificationSerializer,
    UnreadSerializer,
)
from apps.workspaces.access import membership
from apps.workspaces.models import Member

PAGE_SIZE = 30


def _mine(member: Member) -> QuerySet[Notification]:
    """The person's notifications in channels they can still read."""
    return Notification.objects.for_workspace(member.workspace).filter(
        user_id=member.user_id, channel__in=readable_channels(member).values("pk")
    )


class NotificationListView(APIView):
    @extend_schema(
        parameters=[OpenApiParameter("before_id", int, description="The next page.")],
        responses={200: NotificationPageSerializer},
        summary="My notifications, newest first, with how many are unread",
    )
    def get(self, request: Request, slug: str) -> Response:
        member = membership(cast(User, request.user), slug)
        found = _mine(member).select_related("message__author", "message__parent")
        before = request.query_params.get("before_id")
        if before is not None and before.isdigit():
            found = found.filter(pk__lt=int(before))
        page = list(found.order_by("-pk")[: PAGE_SIZE + 1])
        more = len(page) > PAGE_SIZE
        page = page[:PAGE_SIZE]
        prefetch_related_objects([n.message for n in page], *MESSAGE_PREFETCH)
        return Response(
            {
                "unread": _mine(member).filter(read_at__isnull=True).count(),
                "results": NotificationSerializer(page, many=True).data,
                "next": page[-1].pk if more else None,
            }
        )


class NotificationReadView(APIView):
    @extend_schema(
        request=MarkReadSerializer,
        responses={200: UnreadSerializer},
        summary="Mark some or all of my notifications read",
    )
    def post(self, request: Request, slug: str) -> Response:
        member = membership(cast(User, request.user), slug)
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unread = Notification.objects.for_workspace(member.workspace).filter(
            user_id=member.user_id, read_at__isnull=True
        )
        if not serializer.validated_data["all"]:
            unread = unread.filter(pk__in=serializer.validated_data.get("ids", []))
        with transaction.atomic():
            if unread.update(read_at=timezone.now()):
                events.notifications_changed(member.user_id)
        return Response({"unread": _mine(member).filter(read_at__isnull=True).count()})
