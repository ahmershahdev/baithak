import pytest

from apps.core.channels import ChannelKind
from apps.core.conversations import MAX_PEOPLE, key, kind_for


@pytest.mark.parametrize(
    ("people", "expected"),
    [
        (0, None),
        (1, None),
        (2, ChannelKind.DIRECT),
        (3, ChannelKind.GROUP),
        (MAX_PEOPLE, ChannelKind.GROUP),
        (MAX_PEOPLE + 1, None),
    ],
)
def test_kind_for(people: int, expected: ChannelKind | None) -> None:
    assert kind_for(people) == expected


def test_the_same_people_give_the_same_key_in_any_order() -> None:
    assert key([12, 3, 7]) == key([7, 12, 3, 3]) == "~3-7-12"


def test_different_people_give_different_keys() -> None:
    assert key([1, 23]) != key([12, 3])
