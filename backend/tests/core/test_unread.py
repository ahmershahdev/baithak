import pytest

from apps.core.unread import marker_after, unread_count


@pytest.mark.parametrize(
    ("current", "requested", "last_seq", "expected"),
    [
        (0, 5, 10, 5),
        (5, 10, 10, 10),
        (5, 3, 10, 5),
        (5, 5, 10, 5),
        (5, 99, 10, 10),
        (0, 0, 0, 0),
    ],
)
def test_marker_after(current: int, requested: int, last_seq: int, expected: int) -> None:
    assert marker_after(current, requested, last_seq) == expected


@pytest.mark.parametrize(
    ("last_seq", "last_read_seq", "deleted_unread", "expected"),
    [
        (10, 10, 0, 0),
        (10, 4, 0, 6),
        (10, 4, 2, 4),
        (10, 4, 6, 0),
        (10, 4, 9, 0),
    ],
)
def test_unread_count(
    last_seq: int, last_read_seq: int, deleted_unread: int, expected: int
) -> None:
    assert unread_count(last_seq, last_read_seq, deleted_unread) == expected
