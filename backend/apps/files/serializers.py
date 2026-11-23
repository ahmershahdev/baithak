from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.files import links
from apps.files.models import Attachment, Scan

ATTACHMENT_PREFETCH = Prefetch(
    "attachments", queryset=Attachment.objects.select_related("workspace").order_by("id")
)


class AttachmentSerializer(serializers.ModelSerializer[Attachment]):
    """Needs `workspace` loaded for the links."""

    url = serializers.SerializerMethodField(
        help_text="Signed; stops working after a while. Null until the file is scanned clean."
    )
    scan_note = serializers.SerializerMethodField(
        help_text="Why a refused file was removed; empty otherwise."
    )
    preview_url = serializers.SerializerMethodField(
        help_text="A smaller image, once made; null before that and for other files."
    )

    class Meta:
        model = Attachment
        fields = (
            "id",
            "name",
            "content_type",
            "size",
            "width",
            "height",
            "scan",
            "scan_note",
            "url",
            "preview_url",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_url(self, attachment: Attachment) -> str | None:
        if attachment.scan != Scan.CLEAN:
            return None
        return links.url(attachment.workspace.slug, attachment.pk, links.ORIGINAL)

    def get_scan_note(self, attachment: Attachment) -> str:
        if attachment.scan == Scan.INFECTED:
            return "Removed: a virus scan flagged it."
        if attachment.scan == Scan.DAMAGED:
            return f"Removed: {attachment.scan_detail}"
        return ""

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_preview_url(self, attachment: Attachment) -> str | None:
        if not attachment.preview_key or attachment.scan != Scan.CLEAN:
            return None
        return links.url(attachment.workspace.slug, attachment.pk, links.PREVIEW)


class UploadSerializer(serializers.Serializer[None]):
    file = serializers.FileField()
