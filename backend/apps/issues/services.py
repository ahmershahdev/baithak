from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.chat import messages
from apps.core.issues import Status, announce_in_channel, describe, is_closed
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


def _post_activity(issue: Issue, actor: User, body: str, *, to_channel: bool) -> None:
    """Say what happened in the thread of the issue's message, if it has one. An archived
    channel takes no posts, so its message only gets a new event for the link."""
    message = issue.message
    if message is None:
        return
    if message.channel.archived:
        messages.touch(message)
        return
    messages.post(
        message.channel,
        actor,
        body,
        parent=message,
        also_in_channel=to_channel,
        activity=True,
    )


def create_issue(project: Project, author: User, data: dict[str, Any]) -> Issue:
    """Take the project's next number and save the issue, in one transaction. With `message`,
    the issue's opening is posted in that message's thread."""
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
        detail = {"issue": f"{project.key}-{number}", "title": issue.title}
        if issue.message is not None:
            detail["from_message"] = f"{issue.message.channel_id}#{issue.message.seq}"
            _post_activity(
                issue, author, f"opened {detail['issue']}: {issue.title}", to_channel=False
            )
        audit.record(project.workspace, author, "issue.create", issue, detail)
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
            ref = f"{issue.project.key}-{issue.number}"
            logged = _for_log(changes)
            audit.record(
                issue.project.workspace, actor, "issue.update", issue, {"issue": ref, **logged}
            )
            _post_activity(
                issue,
                actor,
                f"{ref}: " + ", ".join(describe(logged)),
                to_channel=announce_in_channel(logged),
            )
    return issue
