from django.conf import settings
from django.db import models

from apps.chat.models import Channel, Message
from apps.workspaces.models import Workspace, WorkspaceScopedManager


class Attachment(models.Model):
    """An uploaded file. It belongs to its uploader until a message they send takes it."""

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="attachments")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="attachments")
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments"
    )
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    name = models.CharField(max_length=200)
    # Sniffed from the bytes (apps/core/files.py), never taken from the browser.
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    # Where it lives under FILES_ROOT, which the web server never serves.
    storage_key = models.CharField(max_length=100, unique=True)
    preview_key = models.CharField(max_length=100, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = WorkspaceScopedManager["Attachment"]()

    def __str__(self) -> str:
        return self.name
