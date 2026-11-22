from typing import Any

import pytest

from apps.core.issues import (
    Priority,
    Status,
    announce_in_channel,
    can_be_assigned,
    can_manage_projects,
    can_view,
    can_work_on_issues,
    describe,
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


class TestDescribe:
    def test_every_field_in_order(self) -> None:
        changes: dict[str, list[Any]] = {
            "issue": ["BAI-1", "BAI-1"],
            "labels": [["bug", "ui"], ["bug", "urgent"]],
            "due": [None, "2026-12-01"],
            "assignee": [None, "bilal"],
            "priority": ["none", "high"],
            "status": ["todo", "in_progress"],
            "description": ["(changed)", "(changed)"],
            "title": ["Old", "Uploads fail"],
        }

        assert describe(changes) == [
            'renamed it to "Uploads fail"',
            "edited the description",
            "moved it to In progress",
            "set priority to high",
            "assigned it to bilal",
            "set it due 2026-12-01",
            "added urgent",
            "removed ui",
        ]

    def test_clearing(self) -> None:
        changes: dict[str, list[Any]] = {
            "priority": ["low", "none"],
            "assignee": ["bilal", None],
            "due": ["2026-12-01", None],
            "labels": [["bug"], []],
        }

        assert describe(changes) == [
            "cleared the priority",
            "unassigned it",
            "cleared the due date",
            "removed bug",
        ]

    def test_only_added_labels(self) -> None:
        assert describe({"labels": [[], ["bug"]]}) == ["added bug"]

    def test_nothing_known_says_nothing(self) -> None:
        assert describe({"issue": ["BAI-1", "BAI-1"]}) == []


@pytest.mark.parametrize(
    ("changes", "expected"),
    [({"status": ["todo", "done"]}, True), ({"title": ["a", "b"]}, False)],
)
def test_only_status_changes_reach_the_channel(
    changes: dict[str, list[object]], expected: bool
) -> None:
    assert announce_in_channel(changes) is expected
