"""Who may do what inside a workspace, decided from roles alone.

Callers look up the roles and counts; these functions only compare them, so every rule can be
read and tested without a database.
"""

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    GUEST = "guest"


_RANK = {Role.GUEST: 0, Role.MEMBER: 1, Role.ADMIN: 2, Role.OWNER: 3}


def outranks_or_equals(role: Role, other: Role) -> bool:
    return _RANK[role] >= _RANK[other]


def is_admin(role: Role) -> bool:
    return outranks_or_equals(role, Role.ADMIN)


def can_edit_workspace(role: Role) -> bool:
    return is_admin(role)


def can_see_audit_log(role: Role) -> bool:
    return is_admin(role)


def can_invite(actor: Role, invited: Role) -> bool:
    # Ownership is never handed out by invitation; an owner promotes an existing member.
    return is_admin(actor) and invited != Role.OWNER and outranks_or_equals(actor, invited)


def can_change_role(actor: Role, target: Role, new: Role, *, owners: int) -> bool:
    """`owners` is how many owners the workspace has now."""
    if not is_admin(actor):
        return False
    # An admin can neither touch someone ranked above them nor give out a rank above their own.
    if not (outranks_or_equals(actor, target) and outranks_or_equals(actor, new)):
        return False
    # A workspace always keeps at least one owner.
    return not (target == Role.OWNER and new != Role.OWNER and owners <= 1)


def can_remove(actor: Role, target: Role, *, is_self: bool, owners: int) -> bool:
    """Removing yourself is leaving. `owners` is how many owners the workspace has now."""
    if target == Role.OWNER and owners <= 1:
        return False
    if is_self:
        return True
    return is_admin(actor) and outranks_or_equals(actor, target)


class OnAccountDeletion(StrEnum):
    LEAVE = "leave"
    DELETE_WORKSPACE = "delete_workspace"
    BLOCK = "block"


def on_account_deletion(role: Role, *, owners: int, members: int) -> OnAccountDeletion:
    """What deleting someone's account does to one workspace they are in. `owners` and
    `members` are the workspace's counts now, the person included."""
    if members <= 1:
        return OnAccountDeletion.DELETE_WORKSPACE
    # The last owner hands the workspace over first; nobody else could ever manage it.
    if role == Role.OWNER and owners <= 1:
        return OnAccountDeletion.BLOCK
    return OnAccountDeletion.LEAVE
