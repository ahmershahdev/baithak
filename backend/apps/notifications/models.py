from typing import ClassVar

from django.conf import settings
from django.db import models

from apps.chat.models import Channel, Message
from apps.core.notifications import Kind
from apps.workspaces.models import Workspace, WorkspaceScopedManager


class Notification(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="notifications")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=10, choices=[(k.value, k.name.title()) for k in Kind])
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="+")
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="notifications")
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = WorkspaceScopedManager["Notification"]()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["user", "message"], name="notification_once")
        ]
        indexes: ClassVar = [
            models.Index(fields=["user", "workspace", "read_at"], name="notification_unread"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} for {self.user_id} on {self.message_id}"
