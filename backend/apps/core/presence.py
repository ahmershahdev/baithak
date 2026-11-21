"""Who is online, and how often typing notices go out.

Each open socket is one entry, "<user id>:<connection>", that lapses TTL seconds after its last
ping (apps/chat/presence.py keeps them in Redis). A person is online while any of their entries
is alive, so a second tab closing doesn't take them offline and a crashed tab drops off alone.
"""

from collections.abc import Iterable

# The web app pings every 25 s; two missed pings and the connection no longer counts.
TTL = 60
# One typing notice per person and place this often; receivers show it for a little longer.
TYPING_EVERY = 3.0


def entry(user_id: int, connection: str) -> str:
    return f"{user_id}:{connection}"


def user_of(value: str) -> int | None:
    head, _, _ = value.partition(":")
    return int(head) if head.isdigit() else None


def online(entries: Iterable[str]) -> set[int]:
    return {user for value in entries if (user := user_of(value)) is not None}


def typing_due(last_sent: float | None, now: float) -> bool:
    return last_sent is None or now - last_sent >= TYPING_EVERY
