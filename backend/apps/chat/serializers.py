from typing import Any

from rest_framework import serializers

from apps.accounts.models import User
from apps.chat.models import Channel, ChannelMember, Message, channel_name_validator
from apps.core.channels import ChannelKind

KIND_CHOICES = [kind.value for kind in ChannelKind]


class ChannelSerializer(serializers.ModelSerializer[Channel]):
    kind = serializers.ChoiceField(choices=KIND_CHOICES, read_only=True)
    archived = serializers.BooleanField(read_only=True)
    is_member = serializers.BooleanField(read_only=True)
    last_read_seq = serializers.IntegerField(read_only=True, allow_null=True)
    unread = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Channel
        fields = (
            "id",
            "name",
            "kind",
            "topic",
            "is_default",
            "archived",
            "is_member",
            "last_seq",
            "last_read_seq",
            "unread",
            "created_at",
        )
        read_only_fields = fields


class ChannelNameField(serializers.CharField):
    # Lowercased and trimmed of a leading "#" before the validators run.
    def to_internal_value(self, data: Any) -> str:
        return super().to_internal_value(data).strip().lstrip("#").lower()


class ChannelCreateSerializer(serializers.Serializer[None]):
    name = ChannelNameField(max_length=81, validators=[channel_name_validator])
    kind = serializers.ChoiceField(choices=KIND_CHOICES, default=ChannelKind.PUBLIC)
    topic = serializers.CharField(max_length=250, required=False, allow_blank=True)


class ChannelUpdateSerializer(serializers.Serializer[None]):
    name = ChannelNameField(max_length=81, validators=[channel_name_validator], required=False)
    topic = serializers.CharField(max_length=250, required=False, allow_blank=True)
    archived = serializers.BooleanField(required=False)


class ChannelMemberSerializer(serializers.ModelSerializer[ChannelMember]):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = ChannelMember
        fields = ("user_id", "username", "display_name", "joined_at")
        read_only_fields = fields


class AddChannelMemberSerializer(serializers.Serializer[None]):
    user_id = serializers.IntegerField()


class ReadSerializer(serializers.Serializer[None]):
    seq = serializers.IntegerField(min_value=0)


class ReadMarkerSerializer(serializers.Serializer[None]):
    channel = serializers.IntegerField()
    last_read_seq = serializers.IntegerField()
    unread = serializers.IntegerField(allow_null=True)


class AuthorSerializer(serializers.Serializer[User]):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)


class MessageSerializer(serializers.ModelSerializer[Message]):
    """Needs `author` and `parent` loaded (select_related) and `mentions` prefetched to avoid
    queries per message."""

    author = AuthorSerializer(read_only=True, allow_null=True)
    deleted = serializers.BooleanField(read_only=True)
    mentions = AuthorSerializer(many=True, read_only=True)
    parent_seq = serializers.IntegerField(
        source="parent.seq", read_only=True, allow_null=True, help_text="The thread's seq."
    )

    class Meta:
        model = Message
        fields = (
            "id",
            "seq",
            "event",
            "parent_seq",
            "thread_seq",
            "also_in_channel",
            "reply_count",
            "last_reply_at",
            "author",
            "body",
            "client_id",
            "created_at",
            "edited_at",
            "deleted",
            "mentions",
            "mentions_channel",
        )
        read_only_fields = fields


class ChannelEventSerializer(serializers.ModelSerializer[Channel]):
    """A channel as broadcast to everyone in it: without `is_member`, which differs per reader."""

    kind = serializers.ChoiceField(choices=KIND_CHOICES, read_only=True)
    archived = serializers.BooleanField(read_only=True)

    class Meta:
        model = Channel
        fields = ("id", "name", "kind", "topic", "is_default", "archived", "last_seq", "created_at")
        read_only_fields = fields
