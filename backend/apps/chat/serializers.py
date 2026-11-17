from typing import Any

from rest_framework import serializers

from apps.chat.models import Channel, ChannelMember, channel_name_validator
from apps.core.channels import ChannelKind

KIND_CHOICES = [kind.value for kind in ChannelKind]


class ChannelSerializer(serializers.ModelSerializer[Channel]):
    kind = serializers.ChoiceField(choices=KIND_CHOICES, read_only=True)
    archived = serializers.BooleanField(read_only=True)
    is_member = serializers.BooleanField(read_only=True)

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
