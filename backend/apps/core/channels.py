"""Who may read, join, post in and manage a channel. The only place this is decided.

The REST API, WebSocket consumers, search and notifications all call these functions, so a
private channel can't leak through a second code path (AGENTS.md).
"""

from enum import StrEnum

from apps.core.roles import Role, is_admin


class ChannelKind(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


def can_read(role: Role | None, kind: ChannelKind, *, is_member: bool) -> bool:
    """`role` is None for someone outside the workspace."""
    if role is None:
        return False
    if kind == ChannelKind.PUBLIC and role != Role.GUEST:
        return True
    # Private channels are for their members only; an admin role does not open them.
    return is_member


def can_join(role: Role | None, kind: ChannelKind, *, archived: bool) -> bool:
    return role is not None and role != Role.GUEST and kind == ChannelKind.PUBLIC and not archived


def can_post(role: Role | None, kind: ChannelKind, *, is_member: bool, archived: bool) -> bool:
    return is_member and not archived and can_read(role, kind, is_member=is_member)


def can_create(role: Role | None) -> bool:
    return role is not None and role != Role.GUEST


def can_manage(role: Role | None, kind: ChannelKind, *, is_creator: bool, is_member: bool) -> bool:
    """Rename, change the topic, archive."""
    if role is None or not can_read(role, kind, is_member=is_member):
        return False
    return is_admin(role) or (is_creator and is_member)


def can_add_member(role: Role | None, *, is_member: bool) -> bool:
    """Bring another workspace member into a channel you are in."""
    return role is not None and role != Role.GUEST and is_member


def can_edit_message(*, is_author: bool, deleted: bool, archived: bool) -> bool:
    return is_author and not deleted and not archived


def can_delete_message(role: Role | None, *, is_author: bool, deleted: bool) -> bool:
    """Authors delete their own; admins clean up anyone's. Works in archived channels too."""
    return role is not None and not deleted and (is_author or is_admin(role))
