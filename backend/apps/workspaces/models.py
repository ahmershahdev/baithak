from typing import ClassVar, Self, TypeVar

from django.conf import settings
from django.db import models

from apps.core.roles import Role


class Workspace(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=50, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


_M = TypeVar("_M", bound=models.Model)


class WorkspaceScopedQuerySet(models.QuerySet[_M]):
    def for_workspace(self, workspace: Workspace) -> Self:
        return self.filter(workspace=workspace)


# Workspace-owned rows are read through for_workspace(), so a query can't forget which
# workspace it is in (AGENTS.md). Model-specific helpers build on it.
class WorkspaceScopedManager(models.Manager[_M]):
    def get_queryset(self) -> WorkspaceScopedQuerySet[_M]:
        return WorkspaceScopedQuerySet(self.model, using=self._db)

    def for_workspace(self, workspace: Workspace) -> WorkspaceScopedQuerySet[_M]:
        return self.get_queryset().for_workspace(workspace)


class Member(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=10, choices=[(r.value, r.name.title()) for r in Role])
    joined_at = models.DateTimeField(auto_now_add=True)

    objects = WorkspaceScopedManager["Member"]()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["workspace", "user"], name="member_once_per_workspace")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.workspace_id} as {self.role}"


class AuditEvent(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="audit_events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    action = models.CharField(max_length=40)
    model = models.CharField(max_length=40)
    object_id = models.CharField(max_length=40)
    changes = models.JSONField(default=dict)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = WorkspaceScopedManager["AuditEvent"]()

    class Meta:
        ordering: ClassVar = ["-at", "-id"]

    def __str__(self) -> str:
        return f"{self.action} {self.model}:{self.object_id}"


class Invitation(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=[(r.value, r.name.title()) for r in Role])
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    # Only the hash: a leaked database can't be used to join. Empty until the email is sent.
    token_hash = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = WorkspaceScopedManager["Invitation"]()

    def __str__(self) -> str:
        return f"{self.email} to {self.workspace_id} as {self.role}"

    @property
    def is_pending(self) -> bool:
        from django.utils import timezone

        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )
