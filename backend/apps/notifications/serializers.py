from rest_framework import serializers

from apps.chat.serializers import MessageSerializer
from apps.core.notifications import Kind
from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer[Notification]):
    kind = serializers.ChoiceField(choices=[k.value for k in Kind], read_only=True)
    channel = serializers.IntegerField(source="channel_id", read_only=True)
    message = MessageSerializer(read_only=True)
    read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ("id", "kind", "channel", "message", "created_at", "read")
        read_only_fields = fields

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
