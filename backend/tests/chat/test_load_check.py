import math

from apps.chat.management.commands.load_check import percentile, summarize


def test_percentile_is_nearest_rank() -> None:
    ordered = [float(n) for n in range(1, 101)]

    assert percentile(ordered, 0.50) == 50
    assert percentile(ordered, 0.95) == 95
    assert percentile(ordered, 0.99) == 99
    assert percentile([7.0], 0.99) == 7


def test_percentile_of_nothing_is_not_a_number() -> None:
    assert math.isnan(percentile([], 0.5))


def test_summarize_sorts_first() -> None:
    stats = summarize([30.0, 10.0, 20.0, 40.0])

    assert stats == {"p50": 20.0, "p95": 40.0, "p99": 40.0, "max": 40.0}


def test_summarize_of_nothing() -> None:
    assert all(math.isnan(value) for value in summarize([]).values())
