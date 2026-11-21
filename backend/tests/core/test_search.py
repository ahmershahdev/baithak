import pytest

from apps.core.search import MAX_TERMS, boolean_query, terms


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("deploy notes", ["deploy", "notes"]),
        ("Deploy DEPLOY deploy", ["deploy"]),
        ("the plan for the launch", ["plan", "launch"]),
        ("ok go to it", []),
        ('+chai -samosa "lunch" @owner (now)*', ["chai", "samosa", "lunch", "owner", "now"]),
        ("chai-time", ["chai", "time"]),
        ("سلام dosto", ["سلام", "dosto"]),
        ("x" * 85 + " real", ["real"]),
        ("", []),
    ],
)
def test_terms(text: str, expected: list[str]) -> None:
    assert terms(text) == expected


def test_terms_stop_at_the_limit() -> None:
    many = " ".join(f"word{i}" for i in range(20))

    assert len(terms(many)) == MAX_TERMS


def test_boolean_query_requires_every_word_as_a_prefix() -> None:
    assert boolean_query(["deploy", "notes"]) == "+deploy* +notes*"
