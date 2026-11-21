"""Projects and issues: keys, statuses, priorities, and who may do what.

Guests see channels they are added to and nothing else, so projects are for members and up.
"""

import re
from enum import StrEnum

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
