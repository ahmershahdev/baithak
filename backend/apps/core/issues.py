"""Projects and issues: keys, statuses, priorities, and who may do what.

Guests see channels they are added to and nothing else, so projects are for members and up.
"""

import re
from enum import StrEnum
from typing import Any

from apps.core.roles import Role, is_admin


class Status(StrEnum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"


# Done and canceled issues are closed; the others are open.
CLOSED = frozenset({Status.DONE, Status.CANCELED})


class Priority(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


_PRIORITY_RANK = {p: rank for rank, p in enumerate(Priority)}

# Issue references read KEY-12, so a key is short, upper case and starts with a letter.
_KEY = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

# A label's color is one of the six brand hues (docs/design.md), never free text.
LABEL_COLORS = ("accent", "ember", "warning", "success", "danger", "info")


def valid_key(key: str) -> bool:
    return bool(_KEY.match(key))


def priority_rank(priority: Priority) -> int:
    """Urgent highest, none lowest, for sorting."""
    return _PRIORITY_RANK[priority]


def is_closed(status: Status) -> bool:
    return status in CLOSED


def can_view(role: Role | None) -> bool:
    return role is not None and role != Role.GUEST


def can_manage_projects(role: Role | None) -> bool:
    """Create, rename and archive projects, and keep their labels."""
    return role is not None and is_admin(role)


def can_work_on_issues(role: Role | None, *, archived: bool) -> bool:
    """Create and change issues; an archived project is read only."""
    return can_view(role) and not archived


def can_be_assigned(role: Role | None) -> bool:
    return can_view(role)


STATUS_NAMES = {
    Status.BACKLOG: "Backlog",
    Status.TODO: "To do",
    Status.IN_PROGRESS: "In progress",
    Status.DONE: "Done",
    Status.CANCELED: "Canceled",
}


def describe(changes: dict[str, list[Any]]) -> list[str]:
    """One phrase per changed field, in the issue's own field order, from an audit diff
    ({field: [old, new]}). Fields it doesn't know (the ref, say) are left out."""
    lines: list[str] = []
    if "title" in changes:
        lines.append(f'renamed it to "{changes["title"][1]}"')
    if "description" in changes:
        lines.append("edited the description")
    if "status" in changes:
        lines.append(f"moved it to {STATUS_NAMES[Status(changes['status'][1])]}")
    if "priority" in changes:
        priority = Priority(changes["priority"][1])
        lines.append(
            "cleared the priority" if priority == Priority.NONE else f"set priority to {priority}"
        )
    if "assignee" in changes:
        who = changes["assignee"][1]
        lines.append(f"assigned it to {who}" if who else "unassigned it")
    if "due" in changes:
        due = changes["due"][1]
        lines.append(f"set it due {due}" if due else "cleared the due date")
    if "labels" in changes:
        before, after = set(changes["labels"][0]), set(changes["labels"][1])
        added, removed = sorted(after - before), sorted(before - after)
        if added:
            lines.append("added " + ", ".join(added))
        if removed:
            lines.append("removed " + ", ".join(removed))
    return lines


def announce_in_channel(changes: dict[str, list[Any]]) -> bool:
    """Status changes reach the whole channel; the rest stay in the issue's thread."""
    return "status" in changes
