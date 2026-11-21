import pytest

from apps.core.channels import ChannelKind
from apps.core.reactions import MAX_DISTINCT, can_add, can_react, is_emoji
from apps.core.roles import Role

# Escapes, not emoji characters, per AGENTS.md.
THUMBS_UP = "\U0001f44d"
THUMBS_UP_DARK = "\U0001f44d\U0001f3ff"
HEART = "❤️"
FAMILY = "\U0001f468‍\U0001f469‍\U0001f467"
FLAG_PK = "\U0001f1f5\U0001f1f0"
KEYCAP_ONE = "1️⃣"
SCOTLAND = "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f"


@pytest.mark.parametrize(
    "text", [THUMBS_UP, THUMBS_UP_DARK, HEART, FAMILY, FLAG_PK, KEYCAP_ONE, SCOTLAND]
)
def test_emoji_are_accepted(text: str) -> None:
    assert is_emoji(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "ok",
        "1",
        "<b>",
        THUMBS_UP + " ",
        THUMBS_UP + "a",
        "‍",
        "\U0001f3ff",
        THUMBS_UP * 17,
    ],
)
def test_anything_else_is_refused(text: str) -> None:
    assert not is_emoji(text)


@pytest.mark.parametrize(
    ("role", "is_member", "archived", "deleted", "expected"),
    [
        (Role.MEMBER, True, False, False, True),
        (Role.GUEST, True, False, False, True),
        (Role.MEMBER, False, False, False, False),
        (Role.MEMBER, True, True, False, False),
        (Role.MEMBER, True, False, True, False),
        (None, True, False, False, False),
    ],
)
def test_can_react(
    role: Role | None, is_member: bool, archived: bool, deleted: bool, expected: bool
) -> None:
    allowed = can_react(
        role, ChannelKind.PUBLIC, is_member=is_member, archived=archived, deleted=deleted
    )
    assert allowed is expected


@pytest.mark.parametrize(
    ("distinct", "present", "expected"),
    [
        (0, False, True),
        (MAX_DISTINCT - 1, False, True),
        (MAX_DISTINCT, False, False),
        (MAX_DISTINCT, True, True),
    ],
)
def test_can_add(distinct: int, present: bool, expected: bool) -> None:
    assert can_add(distinct, present=present) is expected
