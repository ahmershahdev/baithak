from typing import Any

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.chat.message_views import MAX_BODY
from apps.chat.serializers import AuthorSerializer
from apps.core.github import valid_repo
from apps.integrations.models import Webhook, WebhookDelivery

WEBHOOK_KIND_CHOICES = ["github", "incoming"]
DELIVERY_STATUS_CHOICES = ["pending", "posted", "ignored", "failed"]


def delivery_url(webhook: Webhook, token: str) -> str:
    return f"{settings.FRONTEND_URL}/api/v1/hooks/{webhook.kind}/{token}/"


class WebhookSerializer(serializers.ModelSerializer[Webhook]):
    kind = serializers.ChoiceField(choices=WEBHOOK_KIND_CHOICES, read_only=True)
    channel = serializers.IntegerField(source="channel_id", read_only=True)
    url = serializers.SerializerMethodField(
        help_text="Where deliveries go. Null for incoming webhooks: their URL is shown once."
    )
    created_by = AuthorSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Webhook
        fields: tuple[str, ...] = (
            "id",
            "kind",
            "channel",
            "repo",
            "name",
            "url",
            "created_by",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_url(self, webhook: Webhook) -> str | None:
        return delivery_url(webhook, webhook.token) if webhook.kind == "github" else None


class NewWebhookSerializer(WebhookSerializer):
    """Needs `token` in the context: the incoming webhook's token before it was digested."""

    url = serializers.SerializerMethodField()
    secret = serializers.SerializerMethodField(
        help_text="GitHub only, shown once: paste it into GitHub."
    )

    class Meta(WebhookSerializer.Meta):
        fields = (*WebhookSerializer.Meta.fields, "secret")
        read_only_fields = fields

    def get_url(self, webhook: Webhook) -> str:
        return delivery_url(webhook, self.context.get("token") or webhook.token)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_secret(self, webhook: Webhook) -> str | None:
        return webhook.secret or None


class WebhookCreateSerializer(serializers.Serializer[None]):
    kind = serializers.ChoiceField(choices=WEBHOOK_KIND_CHOICES)
    channel_id = serializers.IntegerField()
    repo = serializers.CharField(max_length=140, required=False, help_text="GitHub: owner/name.")
    name = serializers.CharField(
        max_length=40, required=False, help_text="Incoming: the name its messages show."
    )

    def validate_repo(self, value: str) -> str:
        repo = value.strip().removeprefix("https://github.com/").strip("/")
        if not valid_repo(repo):
            raise serializers.ValidationError("Use owner/name, like ahmershahdev/baithak.")
        return repo.lower()

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if data["kind"] == "github" and not data.get("repo"):
            raise serializers.ValidationError({"repo": ["Name the repository."]})
        if data["kind"] == "incoming" and not data.get("name", "").strip():
            raise serializers.ValidationError({"name": ["Give it a name."]})
        return data


class IncomingSerializer(serializers.Serializer[None]):
    text = serializers.CharField(max_length=MAX_BODY, trim_whitespace=True)


class DeliverySerializer(serializers.ModelSerializer[WebhookDelivery]):
    status = serializers.ChoiceField(choices=DELIVERY_STATUS_CHOICES, read_only=True)

    class Meta:
        model = WebhookDelivery
        fields = ("id", "event", "status", "detail", "attempts", "received_at", "finished_at")
        read_only_fields = fields
