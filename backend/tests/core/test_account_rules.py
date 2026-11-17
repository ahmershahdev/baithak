from datetime import UTC, datetime, timedelta

import pytest

from apps.core import handles, passwords
from apps.core.lockout import (
    Escalation,
    LockState,
    after_failure,
    after_success,
    is_blocked,
)

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def fail(state: LockState, times: int, now: datetime = NOW) -> tuple[LockState, list[str]]:
    escalations = []
    for _ in range(times):
        state, escalation = after_failure(state, now)
        if escalation:
            escalations.append(escalation.value)
    return state, escalations


class TestLockoutLadder:
    def test_two_failures_only_count(self) -> None:
        state, escalations = fail(LockState(), 2)

        assert (state.failures, state.level, escalations) == (2, 0, [])
        assert not is_blocked(state, NOW)

    def test_the_third_locks_for_an_hour(self) -> None:
        state, escalations = fail(LockState(), 3)

        assert escalations == ["locked"]
        assert state.locked_until == NOW + timedelta(hours=1)
        assert is_blocked(state, NOW + timedelta(minutes=59))
        assert not is_blocked(state, NOW + timedelta(hours=1))

    def test_attempts_while_locked_do_not_count(self) -> None:
        locked, _ = fail(LockState(), 3)

        state, escalation = after_failure(locked, NOW + timedelta(minutes=5))

        assert (state, escalation) == (locked, None)

    def test_the_ladder_climbs_to_four_hours_a_week_then_a_ban(self) -> None:
        state = LockState()
        seen: list[object] = []
        now = NOW
        for _ in range(4):
            state, escalations = fail(state, 3, now)
            seen += escalations
            if state.locked_until:
                seen.append(state.locked_until - now)
                now = state.locked_until

        assert seen == [
            "locked",
            timedelta(hours=1),
            "locked",
            timedelta(hours=4),
            "suspended",
            timedelta(days=7),
            "banned",
        ]
        assert state.banned
        assert is_blocked(state, now + timedelta(days=3650))

    def test_a_ban_survives_a_correct_password(self) -> None:
        assert after_success(LockState(level=4, banned=True)).banned

    def test_success_clears_count_and_steps(self) -> None:
        state, _ = fail(LockState(), 4, NOW)

        assert after_success(state) == LockState()

    def test_escalation_names(self) -> None:
        assert [e.value for e in Escalation] == ["locked", "suspended", "banned"]


class TestPasswordRules:
    def test_a_strong_password_meets_every_rule(self) -> None:
        assert passwords.missing("Chai-At-Four-42") == []

    @pytest.mark.parametrize(
        ("password", "missing"),
        [
            ("AbC-12defgh", ["at least 12 characters"]),
            ("abcdefghij-12", ["2 uppercase letters"]),
            ("ABCDEFGHIJ-12", ["2 lowercase letters"]),
            ("Abcdefghij-1", ["2 uppercase letters", "2 digits"]),
            ("AbCdefghij12", ["1 symbol"]),
            ("Ab Cd ef gh 12", ["1 symbol"]),
            ("AB-cd-12" + "x" * 121, ["at most 128 characters"]),
        ],
    )
    def test_each_missing_rule_is_named(self, password: str, missing: list[str]) -> None:
        assert passwords.missing(password) == missing


class TestHandles:
    @pytest.mark.parametrize("handle", ["amna", "bilal.khan", "dev-team", "skill", "classic"])
    def test_ordinary_handles_pass(self, handle: str) -> None:
        assert handles.problem(handle) is None

    @pytest.mark.parametrize(
        "handle",
        ["islamabad", "pakistan", "grapes", "crisis", "sheila", "spicy", "allahditta"],
    )
    def test_words_that_contain_a_blocked_word_by_accident_pass(self, handle: str) -> None:
        assert handles.problem(handle) is None

    @pytest.mark.parametrize(
        "handle",
        [
            "hitler",
            "h1tler",
            "hit-ler",
            "h.i.t.l.e.r",
            "killj4ws",
            "kill_jews",
            "kiiilljjeews",
            "faaggot",
            "kkk",
            "muslim",
            "mus1im",
            "nazi88",
            "f.u.c.k",
            "jewish-team",
            "christians",
            "hindu",
            "Hîtlér",
        ],
    )
    def test_hate_and_abuse_are_caught_in_disguise(self, handle: str) -> None:
        assert handles.problem(handle) == "This handle is not allowed."

    @pytest.mark.parametrize("handle", ["admin", "Support", "everyone", "here", "baithak", "r00t"])
    def test_reserved_names(self, handle: str) -> None:
        assert handles.problem(handle) == "This handle is reserved."


def test_offensive_text_in_display_names() -> None:
    assert handles.is_offensive("Hitler Fan")
    assert not handles.is_offensive("Amna Khan")
    assert not handles.is_offensive("Admin Team")
