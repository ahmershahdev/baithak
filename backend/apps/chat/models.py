from typing import ClassVar

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from apps.core.channels import ChannelKind
from apps.workspaces.models import Workspace, WorkspaceScopedManager

channel_name_validator = RegexValidator(
    r"^[a-z0-9][a-z0-9_-]{0,79}$",
    "Use lowercase letters, digits, hyphens or underscores, starting with a letter or digit.",
)


class Channel(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="channels")
    name = models.CharField(max_length=80, validators=[channel_name_validator])
    kind = models.CharField(max_length=10, choices=[(k.value, k.name.title()) for k in ChannelKind])
    topic = models.CharField(max_length=250, blank=True)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    # The sequence of the newest message; the next one takes last_seq + 1 under a row lock.
    last_seq = models.BigIntegerField(default=0)

    objects = WorkspaceScopedManager["Channel"]()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["workspace", "name"], name="channel_name_per_workspace")
        ]

    def __str__(self) -> str:
        return f"#{self.name}"

    @property
    def archived(self) -> bool:
        return self.archived_at is not None


class ChannelMember(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="channel_memberships"
    )
    last_read_seq = models.BigIntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["channel", "user"], name="channel_member_once")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.channel_id}"
