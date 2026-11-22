"""Who hears about a new message, and why."""

from collections.abc import Iterable
from datetime import time, timedelta
from enum import StrEnum


class Kind(StrEnum):
    MENTION = "mention"
    DIRECT = "direct"
    CHANNEL = "channel"
    ASSIGNED = "assigned"


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


def assignee_to_tell(*, actor_id: int | None, before: int | None, after: int | None) -> int | None:
    """Who to tell that an issue is now theirs: the new assignee, unless nothing changed or they
    assigned it to themselves."""
    if after is None or after in (before, actor_id):
        return None
    return after


# Emails go out for these only; @channel would mail everyone for every announcement.
EMAILED_KINDS = frozenset({Kind.MENTION, Kind.DIRECT})
# Unread this long before an email: someone at their desk reads it in the app first.
EMAIL_AFTER = timedelta(minutes=10)


def in_quiet_hours(now: time, start: time | None, end: time | None) -> bool:
    """`now` is the person's local time. Quiet hours may cross midnight (22:00 to 07:00);
    the start is inside them and the end is not."""
    if start is None or end is None or start == end:
        return False
    if start < end:
        return start <= now < end
    return now >= start or now < end
