from itertools import pairwise

import pytest

from apps.core.roles import (
    OnAccountDeletion,
    Role,
    can_change_role,
    can_edit_workspace,
    can_invite,
    can_remove,
    can_see_audit_log,
    is_admin,
    on_account_deletion,
    outranks_or_equals,
)

OWNER, ADMIN, MEMBER, GUEST = Role.OWNER, Role.ADMIN, Role.MEMBER, Role.GUEST


def test_rank_order() -> None:
    order = [GUEST, MEMBER, ADMIN, OWNER]
    for low, high in pairwise(order):
        assert outranks_or_equals(high, low)
        assert not outranks_or_equals(low, high)
    assert outranks_or_equals(MEMBER, MEMBER)


@pytest.mark.parametrize(
    ("role", "expected"), [(OWNER, True), (ADMIN, True), (MEMBER, False), (GUEST, False)]
)
def test_admin_level_actions(role: Role, expected: bool) -> None:
    assert is_admin(role) is expected
    assert can_edit_workspace(role) is expected
    assert can_see_audit_log(role) is expected


@pytest.mark.parametrize(
    ("actor", "invited", "expected"),
    [
        (OWNER, ADMIN, True),
        (OWNER, GUEST, True),
        (OWNER, OWNER, False),
        (ADMIN, ADMIN, True),
        (ADMIN, MEMBER, True),
        (ADMIN, OWNER, False),
        (MEMBER, MEMBER, False),
        (MEMBER, GUEST, False),
        (GUEST, GUEST, False),
    ],
)
def test_can_invite(actor: Role, invited: Role, expected: bool) -> None:
    assert can_invite(actor, invited) is expected


@pytest.mark.parametrize(
    ("actor", "target", "new", "owners", "expected"),
    [
        (OWNER, MEMBER, ADMIN, 1, True),
        (OWNER, ADMIN, OWNER, 1, True),
        (OWNER, OWNER, ADMIN, 2, True),
        (OWNER, OWNER, ADMIN, 1, False),
        (ADMIN, MEMBER, ADMIN, 1, True),
        (ADMIN, GUEST, MEMBER, 1, True),
        (ADMIN, ADMIN, MEMBER, 1, True),
        (ADMIN, MEMBER, OWNER, 1, False),
        (ADMIN, OWNER, ADMIN, 2, False),
        (MEMBER, GUEST, MEMBER, 1, False),
        (GUEST, GUEST, MEMBER, 1, False),
    ],
)
def test_can_change_role(actor: Role, target: Role, new: Role, owners: int, expected: bool) -> None:
    assert can_change_role(actor, target, new, owners=owners) is expected


@pytest.mark.parametrize(
    ("actor", "target", "is_self", "owners", "expected"),
    [
        (MEMBER, MEMBER, True, 1, True),
        (GUEST, GUEST, True, 1, True),
        (OWNER, OWNER, True, 2, True),
        (OWNER, OWNER, True, 1, False),
        (OWNER, OWNER, False, 2, True),
        (OWNER, ADMIN, False, 1, True),
        (ADMIN, ADMIN, False, 1, True),
        (ADMIN, MEMBER, False, 1, True),
        (ADMIN, OWNER, False, 2, False),
        (MEMBER, GUEST, False, 1, False),
        (GUEST, MEMBER, False, 1, False),
    ],
)
def test_can_remove(actor: Role, target: Role, is_self: bool, owners: int, expected: bool) -> None:
    assert can_remove(actor, target, is_self=is_self, owners=owners) is expected


LEAVE, DELETE, BLOCK = (
    OnAccountDeletion.LEAVE,
    OnAccountDeletion.DELETE_WORKSPACE,
    OnAccountDeletion.BLOCK,
)


@pytest.mark.parametrize(
    ("role", "owners", "members", "expected"),
    [
        (OWNER, 1, 1, DELETE),
        (OWNER, 1, 2, BLOCK),
        (OWNER, 2, 3, LEAVE),
        (ADMIN, 1, 2, LEAVE),
        (MEMBER, 1, 5, LEAVE),
        (GUEST, 1, 2, LEAVE),
    ],
)
def test_on_account_deletion(
    role: Role, owners: int, members: int, expected: OnAccountDeletion
) -> None:
    assert on_account_deletion(role, owners=owners, members=members) is expected
