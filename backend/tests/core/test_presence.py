import pytest

from apps.core.presence import TYPING_EVERY, entry, online, typing_due, user_of


def test_an_entry_names_its_person() -> None:
    assert user_of(entry(42, "specific.abc!def")) == 42


@pytest.mark.parametrize("value", ["", "x:abc", ":abc", "-1:abc"])
def test_a_malformed_entry_names_nobody(value: str) -> None:
    assert user_of(value) is None


def test_several_tabs_count_once_and_junk_is_skipped() -> None:
    assert online([entry(1, "a"), entry(1, "b"), entry(2, "c"), "junk"]) == {1, 2}


@pytest.mark.parametrize(
    ("last_sent", "now", "expected"),
    [
        (None, 100.0, True),
        (100.0, 100.0 + TYPING_EVERY - 0.1, False),
        (100.0, 100.0 + TYPING_EVERY, True),
    ],
)
def test_typing_due(last_sent: float | None, now: float, expected: bool) -> None:
    assert typing_due(last_sent, now) is expected
