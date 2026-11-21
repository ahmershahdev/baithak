import pytest

from apps.core.issues import (
    Priority,
    Status,
    can_be_assigned,
    can_manage_projects,
    can_view,
    can_work_on_issues,
    is_closed,
    priority_rank,
    valid_key,
)
from apps.core.roles import Role

OWNER, ADMIN, MEMBER, GUEST = Role.OWNER, Role.ADMIN, Role.MEMBER, Role.GUEST


@pytest.mark.parametrize(
    ("key", "valid"),
    [
        ("BAI", True),
        ("OPS2", True),
        ("AB", True),
        ("ABCDEFGHIJ", True),
        ("A", False),
        ("ABCDEFGHIJK", False),
        ("bai", False),
        ("2FA", False),
        ("BA-I", False),
        ("", False),
    ],
)
def test_valid_key(key: str, valid: bool) -> None:
    assert valid_key(key) is valid


def test_priorities_sort_from_none_to_urgent() -> None:
    ranks = [priority_rank(p) for p in Priority]

    assert ranks == sorted(ranks)
    assert priority_rank(Priority.URGENT) > priority_rank(Priority.HIGH)


@pytest.mark.parametrize(
    ("status", "closed"),
    [
        (Status.BACKLOG, False),
        (Status.TODO, False),
        (Status.IN_PROGRESS, False),
        (Status.DONE, True),
        (Status.CANCELED, True),
    ],
)
def test_is_closed(status: Status, closed: bool) -> None:
    assert is_closed(status) is closed


@pytest.mark.parametrize(
    ("role", "view", "manage"),
    [
        (OWNER, True, True),
        (ADMIN, True, True),
        (MEMBER, True, False),
        (GUEST, False, False),
        (None, False, False),
    ],
)
def test_who_sees_and_manages_projects(role: Role | None, view: bool, manage: bool) -> None:
    assert can_view(role) is view
    assert can_manage_projects(role) is manage
    assert can_be_assigned(role) is view


@pytest.mark.parametrize(
    ("role", "archived", "expected"),
    [
        (MEMBER, False, True),
        (MEMBER, True, False),
        (GUEST, False, False),
        (None, False, False),
    ],
)
def test_can_work_on_issues(role: Role | None, archived: bool, expected: bool) -> None:
    assert can_work_on_issues(role, archived=archived) is expected
