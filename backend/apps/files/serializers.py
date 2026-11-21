from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.files import links
from apps.files.models import Attachment

ATTACHMENT_PREFETCH = Prefetch(
    "attachments", queryset=Attachment.objects.select_related("workspace").order_by("id")
)


class AttachmentSerializer(serializers.ModelSerializer[Attachment]):
    """Needs `workspace` loaded for the links."""

    url = serializers.SerializerMethodField(help_text="Signed; stops working after a while.")
    preview_url = serializers.SerializerMethodField(
        help_text="A smaller image, once made; null before that and for other files."
    )

    class Meta:
        model = Attachment
        fields = ("id", "name", "content_type", "size", "width", "height", "url", "preview_url")
        read_only_fields = fields

    def get_url(self, attachment: Attachment) -> str:
        return links.url(attachment.workspace.slug, attachment.pk, links.ORIGINAL)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_preview_url(self, attachment: Attachment) -> str | None:
        if not attachment.preview_key:
            return None
        return links.url(attachment.workspace.slug, attachment.pk, links.PREVIEW)


class UploadSerializer(serializers.Serializer[None]):
    file = serializers.FileField()
