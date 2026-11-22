from typing import ClassVar

from django.conf import settings
from django.db import models

from apps.core.issues import LABEL_COLORS, Priority, Status
from apps.workspaces.models import Workspace, WorkspaceScopedManager


class Project(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="projects")
    key = models.CharField(max_length=10)
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    # The next issue's number. It moves only under a lock on this row (apps/issues/services.py),
    # and issues are never deleted, so numbers have no gaps.
    next_number = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = WorkspaceScopedManager["Project"]()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["workspace", "key"], name="project_key_per_workspace")
        ]

    def __str__(self) -> str:
        return self.key

    @property
    def archived(self) -> bool:
        return self.archived_at is not None


class Label(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="labels")
    name = models.CharField(max_length=40)
    color = models.CharField(max_length=10, choices=[(c, c.title()) for c in LABEL_COLORS])

    objects = WorkspaceScopedManager["Label"]()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["project", "name"], name="label_name_per_project")
        ]

    def __str__(self) -> str:
        return self.name


class Issue(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="issues")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="issues")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=12, choices=[(s.value, s.name.title()) for s in Status], default=Status.TODO
    )
    priority = models.CharField(
        max_length=8, choices=[(p.value, p.name.title()) for p in Priority], default=Priority.NONE
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_issues",
    )
    due = models.DateField(null=True, blank=True)
    labels = models.ManyToManyField(Label, blank=True, related_name="issues")
    # Its thread is the issue's discussion. Message rows are never deleted, only their text.
    message = models.OneToOneField(
        "chat.Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issue",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = WorkspaceScopedManager["Issue"]()

    class Meta:
        constraints: ClassVar = [
            models.UniqueConstraint(fields=["project", "number"], name="issue_number_per_project")
        ]
        indexes: ClassVar = [models.Index(fields=["project", "status"], name="issue_status")]

    def __str__(self) -> str:
        return f"{self.project_id}-{self.number}"
