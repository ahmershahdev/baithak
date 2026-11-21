"""What counts as a reaction, and who may react.

A reaction is one emoji: pictographs, flags, keycaps, skin tones and ZWJ sequences, written in
any combination Unicode uses for a single emoji. Text and markup are refused, so the field
can't carry a message of its own.
"""

import unicodedata

from apps.core.channels import ChannelKind, can_post
from apps.core.roles import Role

MAX_LENGTH = 16
MAX_DISTINCT = 20

_ZWJ = 0x200D
_KEYCAP = 0x20E3
_JOINERS = {_ZWJ, 0xFE0E, 0xFE0F, _KEYCAP}
_SKIN_TONES = range(0x1F3FB, 0x1F400)
_TAGS = range(0xE0020, 0xE0080)
_KEYCAP_BASES = set("0123456789#*")


def is_emoji(text: str) -> bool:
    if not 1 <= len(text) <= MAX_LENGTH:
        return False
    keycap = chr(_KEYCAP) in text
    pictured = False
    for char in text:
        point = ord(char)
        if unicodedata.category(char) == "So":
            pictured = True
        elif (
            point in _JOINERS
            or point in _SKIN_TONES
            or point in _TAGS
            or (keycap and char in _KEYCAP_BASES)
        ):
            continue
        else:
            return False
    return pictured or keycap


def can_react(
    role: Role | None, kind: ChannelKind, *, is_member: bool, archived: bool, deleted: bool
) -> bool:
    return not deleted and can_post(role, kind, is_member=is_member, archived=archived)


def can_add(distinct: int, *, present: bool) -> bool:
    """A message holds up to MAX_DISTINCT different emoji; more people can always join one."""
    return present or distinct < MAX_DISTINCT
