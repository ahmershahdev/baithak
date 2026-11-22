from django.conf import settings
from rest_framework import serializers

from apps.chat.serializers import AuthorSerializer
from apps.core.github import valid_repo
from apps.integrations.models import Webhook

WEBHOOK_KIND_CHOICES = ["github"]


def delivery_url(webhook: Webhook) -> str:
    return f"{settings.FRONTEND_URL}/api/v1/hooks/{webhook.kind}/{webhook.token}/"


class WebhookSerializer(serializers.ModelSerializer[Webhook]):
    kind = serializers.ChoiceField(choices=WEBHOOK_KIND_CHOICES, read_only=True)
    channel = serializers.IntegerField(source="channel_id", read_only=True)
    url = serializers.SerializerMethodField(help_text="Where GitHub sends deliveries.")
    created_by = AuthorSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Webhook
        fields: tuple[str, ...] = (
            "id",
            "kind",
            "channel",
            "repo",
            "url",
            "created_by",
            "created_at",
        )
        read_only_fields = fields

    def get_url(self, webhook: Webhook) -> str:
        return delivery_url(webhook)


class NewWebhookSerializer(WebhookSerializer):
    secret = serializers.CharField(
        read_only=True, help_text="Shown once, when made: paste it into GitHub."
    )

    class Meta(WebhookSerializer.Meta):
        fields = (*WebhookSerializer.Meta.fields, "secret")
        read_only_fields = fields


class WebhookCreateSerializer(serializers.Serializer[None]):
    kind = serializers.ChoiceField(choices=WEBHOOK_KIND_CHOICES)
    channel_id = serializers.IntegerField()
    repo = serializers.CharField(max_length=140, help_text="owner/name")

    def validate_repo(self, value: str) -> str:
        repo = value.strip().removeprefix("https://github.com/").strip("/")
        if not valid_repo(repo):
            raise serializers.ValidationError("Use owner/name, like ahmershahdev/baithak.")
        return repo.lower()
