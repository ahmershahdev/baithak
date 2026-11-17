import pytest

from apps.core.channels import (
    ChannelKind,
    can_add_member,
    can_create,
    can_join,
    can_manage,
    can_post,
    can_read,
)
from apps.core.roles import Role

OWNER, ADMIN, MEMBER, GUEST = Role.OWNER, Role.ADMIN, Role.MEMBER, Role.GUEST
PUBLIC, PRIVATE = ChannelKind.PUBLIC, ChannelKind.PRIVATE


@pytest.mark.parametrize(
    ("role", "kind", "is_member", "expected"),
    [
        (None, PUBLIC, False, False),
        (None, PUBLIC, True, False),
        (OWNER, PUBLIC, False, True),
        (ADMIN, PUBLIC, False, True),
        (MEMBER, PUBLIC, False, True),
        (GUEST, PUBLIC, False, False),
        (GUEST, PUBLIC, True, True),
        (OWNER, PRIVATE, False, False),
        (ADMIN, PRIVATE, False, False),
        (MEMBER, PRIVATE, False, False),
        (MEMBER, PRIVATE, True, True),
        (GUEST, PRIVATE, True, True),
    ],
)
def test_can_read(role: Role | None, kind: ChannelKind, is_member: bool, expected: bool) -> None:
    assert can_read(role, kind, is_member=is_member) is expected


@pytest.mark.parametrize(
    ("role", "kind", "archived", "expected"),
    [
        (MEMBER, PUBLIC, False, True),
        (ADMIN, PUBLIC, False, True),
        (MEMBER, PUBLIC, True, False),
        (MEMBER, PRIVATE, False, False),
        (GUEST, PUBLIC, False, False),
        (None, PUBLIC, False, False),
    ],
)
def test_can_join(role: Role | None, kind: ChannelKind, archived: bool, expected: bool) -> None:
    assert can_join(role, kind, archived=archived) is expected


@pytest.mark.parametrize(
    ("role", "kind", "is_member", "archived", "expected"),
    [
        (MEMBER, PUBLIC, True, False, True),
        (MEMBER, PUBLIC, False, False, False),
        (MEMBER, PUBLIC, True, True, False),
        (GUEST, PUBLIC, True, False, True),
        (GUEST, PRIVATE, True, False, True),
        (None, PUBLIC, True, False, False),
    ],
)
def test_can_post(
    role: Role | None, kind: ChannelKind, is_member: bool, archived: bool, expected: bool
) -> None:
    assert can_post(role, kind, is_member=is_member, archived=archived) is expected


@pytest.mark.parametrize(
    ("role", "expected"),
    [(OWNER, True), (ADMIN, True), (MEMBER, True), (GUEST, False), (None, False)],
)
def test_can_create(role: Role | None, expected: bool) -> None:
    assert can_create(role) is expected


@pytest.mark.parametrize(
    ("role", "kind", "is_creator", "is_member", "expected"),
    [
        (ADMIN, PUBLIC, False, False, True),
        (OWNER, PUBLIC, False, False, True),
        (ADMIN, PRIVATE, False, True, True),
        (ADMIN, PRIVATE, False, False, False),
        (MEMBER, PUBLIC, True, True, True),
        (MEMBER, PUBLIC, True, False, False),
        (MEMBER, PUBLIC, False, True, False),
        (MEMBER, PRIVATE, True, True, True),
        (GUEST, PUBLIC, False, True, False),
        (None, PUBLIC, True, True, False),
    ],
)
def test_can_manage(
    role: Role | None, kind: ChannelKind, is_creator: bool, is_member: bool, expected: bool
) -> None:
    assert can_manage(role, kind, is_creator=is_creator, is_member=is_member) is expected


@pytest.mark.parametrize(
    ("role", "is_member", "expected"),
    [
        (MEMBER, True, True),
        (ADMIN, True, True),
        (MEMBER, False, False),
        (GUEST, True, False),
        (None, True, False),
    ],
)
def test_can_add_member(role: Role | None, is_member: bool, expected: bool) -> None:
    assert can_add_member(role, is_member=is_member) is expected
