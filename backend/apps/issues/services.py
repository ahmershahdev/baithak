from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.issues import Status, is_closed
from apps.issues.models import Issue, Label, Project
from apps.workspaces import audit


def _state(issue: Issue) -> dict[str, Any]:
    """What the audit log keeps of an issue: not its description, just whether it changed."""
    return {
        "title": issue.title,
        "description": issue.description,
        "status": issue.status,
        "priority": issue.priority,
        "assignee": issue.assignee.username if issue.assignee else None,
        "due": issue.due.isoformat() if issue.due else None,
        "labels": sorted(label.name for label in issue.labels.all()),
    }


def _for_log(changes: dict[str, list[Any]]) -> dict[str, list[Any]]:
    if "description" in changes:
        changes["description"] = ["(changed)", "(changed)"]
    return changes


def create_issue(project: Project, author: User, data: dict[str, Any]) -> Issue:
    """Take the project's next number and save the issue, in one transaction."""
    labels: list[Label] = data.pop("labels", [])
    with transaction.atomic():
        locked = Project.objects.select_for_update().get(pk=project.pk)
        number = locked.next_number
        locked.next_number += 1
        locked.save(update_fields=["next_number"])
        issue = Issue.objects.create(
            workspace_id=project.workspace_id,
            project=locked,
            number=number,
            created_by=author,
            closed_at=timezone.now()
            if is_closed(Status(data.get("status", Status.TODO)))
            else None,
            **data,
        )
        issue.labels.set(labels)
        audit.record(
            project.workspace,
            author,
            "issue.create",
            issue,
            {"issue": f"{project.key}-{number}", "title": issue.title},
        )
    return issue


def update_issue(issue: Issue, actor: User, data: dict[str, Any]) -> Issue:
    labels: list[Label] | None = data.pop("labels", None)
    with transaction.atomic():
        before = _state(issue)
        was_closed = is_closed(Status(issue.status))
        for field, value in data.items():
            setattr(issue, field, value)
        now_closed = is_closed(Status(issue.status))
        if now_closed and not was_closed:
            issue.closed_at = timezone.now()
        elif was_closed and not now_closed:
            issue.closed_at = None
        issue.save()
        if labels is not None:
            issue.labels.set(labels)
        changes = audit.diff(before, _state(issue))
        if changes:
            audit.record(
                issue.project.workspace,
                actor,
                "issue.update",
                issue,
                {"issue": f"{issue.project.key}-{issue.number}", **_for_log(changes)},
            )
    return issue
