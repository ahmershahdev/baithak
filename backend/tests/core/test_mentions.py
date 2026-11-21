import pytest

from apps.core.mentions import can_mention_channel, parse
from apps.core.roles import Role


@pytest.mark.parametrize(
    ("body", "handles", "channel"),
    [
        ("no mentions here", set(), False),
        ("@amna salaam", {"amna"}, False),
        ("salaam @Amna and @bilal_k", {"amna", "bilal_k"}, False),
        ("thanks @amna.", {"amna"}, False),
        ("@amna, @amna!", {"amna"}, False),
        ("(@ali.raza)", {"ali.raza"}, False),
        ("mail amna@example.com", set(), False),
        ("@@amna", set(), False),
        ("@a is too short", set(), False),
        ("@" + "x" * 31 + " is too long", set(), False),
        ("@channel lunch is here", set(), True),
        ("@Channel and @amna", {"amna"}, True),
        ("@channels is a person", {"channels"}, False),
        ("@ alone", set(), False),
        ("@_amna starts badly", set(), False),
    ],
)
def test_parse(body: str, handles: set[str], channel: bool) -> None:
    found = parse(body)

    assert (set(found.handles), found.channel) == (handles, channel)


@pytest.mark.parametrize(
    ("role", "expected"),
    [(Role.OWNER, True), (Role.ADMIN, True), (Role.MEMBER, True), (Role.GUEST, False)],
)
def test_can_mention_channel(role: Role, expected: bool) -> None:
    assert can_mention_channel(role) is expected
