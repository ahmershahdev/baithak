from datetime import time

import pytest

from apps.core.notifications import Kind, in_quiet_hours, recipients

AUTHOR, BILAL, SARA, ZAIN = 1, 2, 3, 4


def test_a_mention_tells_only_the_person_named() -> None:
    found = recipients(
        author_id=AUTHOR, mentioned=[BILAL], channel_wide=False, members=[], conversation=False
    )

    assert found == {BILAL: Kind.MENTION}


def test_at_channel_tells_every_member_but_the_author() -> None:
    found = recipients(
        author_id=AUTHOR,
        mentioned=[],
        channel_wide=True,
        members=[AUTHOR, BILAL, SARA],
        conversation=False,
    )

    assert found == {BILAL: Kind.CHANNEL, SARA: Kind.CHANNEL}


def test_a_conversation_tells_everyone_in_it_and_a_mention_wins() -> None:
    found = recipients(
        author_id=AUTHOR,
        mentioned=[SARA],
        channel_wide=True,
        members=[AUTHOR, BILAL, SARA, ZAIN],
        conversation=True,
    )

    assert found == {BILAL: Kind.DIRECT, SARA: Kind.MENTION, ZAIN: Kind.DIRECT}


def test_mentioning_yourself_tells_nobody() -> None:
    found = recipients(
        author_id=AUTHOR, mentioned=[AUTHOR], channel_wide=False, members=[], conversation=False
    )

    assert found == {}


def test_a_message_whose_author_is_gone_still_tells_people() -> None:
    found = recipients(
        author_id=None, mentioned=[BILAL], channel_wide=False, members=[], conversation=False
    )

    assert found == {BILAL: Kind.MENTION}


@pytest.mark.parametrize(
    ("now", "start", "end", "quiet"),
    [
        (time(23, 0), None, None, False),
        (time(23, 0), time(22, 0), None, False),
        (time(23, 0), time(9, 0), time(9, 0), False),
        (time(13, 0), time(12, 0), time(14, 0), True),
        (time(12, 0), time(12, 0), time(14, 0), True),
        (time(14, 0), time(12, 0), time(14, 0), False),
        (time(23, 30), time(22, 0), time(7, 0), True),
        (time(3, 0), time(22, 0), time(7, 0), True),
        (time(7, 0), time(22, 0), time(7, 0), False),
        (time(12, 0), time(22, 0), time(7, 0), False),
    ],
)
def test_in_quiet_hours(now: time, start: time | None, end: time | None, quiet: bool) -> None:
    assert in_quiet_hours(now, start, end) is quiet
