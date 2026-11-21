from typing import Any

from rest_framework import serializers

from apps.chat.models import Message
from apps.chat.serializers import MessageSerializer
from apps.files.models import Attachment
from apps.files.serializers import AttachmentSerializer


class SearchParamsSerializer(serializers.Serializer[None]):
    q = serializers.CharField(max_length=200, help_text="Words to find, each as a prefix.")
    channel = serializers.IntegerField(required=False)
    author = serializers.CharField(required=False, max_length=30, help_text="A @handle.")
    after = serializers.DateField(required=False, help_text="On or after this day.")
    before = serializers.DateField(required=False, help_text="On or before this day.")
    before_id = serializers.IntegerField(
        required=False, help_text="The next page: `next` from the last."
    )

    def validate_author(self, value: str) -> str:
        return value.strip().lstrip("@").lower()

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        after, before = data.get("after"), data.get("before")
        if after and before and after > before:
            raise serializers.ValidationError({"before": ["Pick a day after the start."]})
        return data


class MessageHitSerializer(serializers.Serializer[Message]):
    channel = serializers.IntegerField(source="channel_id")
    message = MessageSerializer(source="*")


class MessageResultsSerializer(serializers.Serializer[None]):
    terms = serializers.ListField(
        child=serializers.CharField(), help_text="The words searched for; empty when none counted."
    )
    results = MessageHitSerializer(many=True)
    next = serializers.IntegerField(allow_null=True)


class FileHitSerializer(serializers.Serializer[Attachment]):
    channel = serializers.IntegerField(source="channel_id")
    message_seq = serializers.IntegerField(source="message.seq", allow_null=True)
    parent_seq = serializers.IntegerField(source="message.parent.seq", allow_null=True)
    file = AttachmentSerializer(source="*")


class FileResultsSerializer(serializers.Serializer[None]):
    terms = serializers.ListField(child=serializers.CharField())
    results = FileHitSerializer(many=True)
    next = serializers.IntegerField(allow_null=True)
