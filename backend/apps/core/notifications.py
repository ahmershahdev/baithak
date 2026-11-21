"""Who hears about a new message, and why."""

from collections.abc import Iterable
from enum import StrEnum


class Kind(StrEnum):
    MENTION = "mention"
    DIRECT = "direct"
    CHANNEL = "channel"


def recipients(
    *,
    author_id: int | None,
    mentioned: Iterable[int],
    channel_wide: bool,
    members: Iterable[int],
    conversation: bool,
) -> dict[int, Kind]:
    """One reason per person, the strongest: named, then in a direct or group conversation,
    then @channel. `members` are the channel's members; `mentioned` were already limited to
    people who can read the channel. The author is never told about their own message."""
    found: dict[int, Kind] = {}
    people = set(members)
    if channel_wide:
        found |= dict.fromkeys(people, Kind.CHANNEL)
    if conversation:
        found |= dict.fromkeys(people, Kind.DIRECT)
    found |= dict.fromkeys(mentioned, Kind.MENTION)
    if author_id is not None:
        found.pop(author_id, None)
    return found
