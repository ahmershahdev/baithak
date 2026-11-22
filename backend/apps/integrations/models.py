from django.conf import settings
from django.db import models

from apps.chat.models import Channel
from apps.workspaces.models import Workspace, WorkspaceScopedManager


class Webhook(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="webhooks")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="webhooks")
    kind = models.CharField(max_length=10, choices=[("github", "GitHub"), ("incoming", "Incoming")])
    # GitHub: owner/name; deliveries about any other repository are ignored.
    repo = models.CharField(max_length=140, blank=True)
    # Incoming: the name its messages are shown under.
    name = models.CharField(max_length=40, blank=True)
    # Finds the webhook from its URL. GitHub: the token itself, which proves nothing (the
    # signature does). Incoming: the token is the proof, so only its digest is kept
    # (apps/core/webhooks.py).
    token = models.CharField(max_length=64, unique=True)
    # GitHub's HMAC key, kept as is since checking a signature needs it. Empty for incoming.
    secret = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = WorkspaceScopedManager["Webhook"]()

    def __str__(self) -> str:
        return f"{self.kind} {self.repo} -> {self.channel_id}"
