from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.chat.serializers import AuthorSerializer, MessageSerializer
from apps.core.notifications import Kind
from apps.notifications.models import Notification


class NotificationIssueSerializer(serializers.Serializer[None]):
    ref = serializers.CharField(help_text="KEY-12")
    project = serializers.CharField()
    number = serializers.IntegerField()
    title = serializers.CharField()


class NotificationSerializer(serializers.ModelSerializer[Notification]):
    """Either `channel` and `message` are set, or `issue` (kind `assigned`)."""

    kind = serializers.ChoiceField(choices=[k.value for k in Kind], read_only=True)
    channel = serializers.IntegerField(source="channel_id", read_only=True, allow_null=True)
    message = MessageSerializer(read_only=True, allow_null=True)
    issue = serializers.SerializerMethodField()
    actor = AuthorSerializer(
        read_only=True,
        allow_null=True,
        help_text="Who assigned the issue; null for message notifications (see the author).",
    )
    read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ("id", "kind", "channel", "message", "issue", "actor", "created_at", "read")
        read_only_fields = fields

    @extend_schema_field(NotificationIssueSerializer(allow_null=True))
    def get_issue(self, notification: Notification) -> dict[str, Any] | None:
        issue = notification.issue
        if issue is None:
            return None
        key = issue.project.key
        return {
            "ref": f"{key}-{issue.number}",
            "project": key,
            "number": issue.number,
            "title": issue.title,
        }

    def get_read(self, notification: Notification) -> bool:
        return notification.read_at is not None


class NotificationPageSerializer(serializers.Serializer[None]):
    unread = serializers.IntegerField()
    results = NotificationSerializer(many=True)
    next = serializers.IntegerField(allow_null=True)


class MarkReadSerializer(serializers.Serializer[None]):
    ids = serializers.ListField(child=serializers.IntegerField(), required=False, max_length=100)
    all = serializers.BooleanField(default=False)


class UnreadSerializer(serializers.Serializer[None]):
    unread = serializers.IntegerField()
