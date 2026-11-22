"""Finding @mentions in a message body.

`@handle` names a person by their handle (2 to 30 of a-z 0-9 . _ -, starting with a letter or
digit); `@channel` names everyone in the channel. "channel" is a reserved handle (handles.py),
so nobody can own it.
"""

import re
from dataclasses import dataclass

from apps.core.roles import Role

CHANNEL = "channel"

# Not after a word character, "@" or ".": "amna@example.com" and "@@amna" mention nobody.
_MENTION = re.compile(r"(?<![\w@.])@([A-Za-z0-9][A-Za-z0-9_.-]*)")
# Code blocks and inline code, as frontend/src/chat/format.ts reads them: a handle shown as code
# is quoted, not addressed, so it notifies nobody.
_CODE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)


@dataclass(frozen=True)
class Mentions:
    handles: frozenset[str]
    channel: bool


def parse(body: str) -> Mentions:
    handles: set[str] = set()
    channel = False
    for match in _MENTION.finditer(_CODE.sub(" ", body)):
        # A sentence ending right after a handle ("thanks @amna.") ends the handle too; handles
        # may end in . _ or - but then can't be mentioned at the end of a sentence.
        handle = match.group(1).lower().rstrip("._-")
        if handle == CHANNEL:
            channel = True
        elif 2 <= len(handle) <= 30:
            handles.add(handle)
    return Mentions(frozenset(handles), channel)


def can_mention_channel(role: Role) -> bool:
    """Guests can't ping everyone in a channel."""
    return role != Role.GUEST
