from django.conf import settings
from django.db import models

from apps.chat.models import Channel
from apps.workspaces.models import Workspace, WorkspaceScopedManager


class Webhook(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="webhooks")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="webhooks")
    kind = models.CharField(max_length=10, choices=[("github", "GitHub")])
    # owner/name; deliveries about any other repository are ignored.
    repo = models.CharField(max_length=140, blank=True)
    # In the delivery URL, so it finds the webhook; it proves nothing by itself.
    token = models.CharField(max_length=64, unique=True)
    # The HMAC key GitHub signs with. Kept as is, since checking a signature needs the key.
    secret = models.CharField(max_length=64)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = WorkspaceScopedManager["Webhook"]()

    def __str__(self) -> str:
        return f"{self.kind} {self.repo} -> {self.channel_id}"
