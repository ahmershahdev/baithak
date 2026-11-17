"""The lockout ladder for one account, shared by sign-in and password-reset codes.

Every third wrong attempt climbs one step: 1 hour, 4 hours, a week's suspension, then a ban
that only an admin lifts. A correct attempt clears the count and the steps.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

FAILURES_PER_STEP = 3
STEPS = (timedelta(hours=1), timedelta(hours=4), timedelta(days=7))


class Escalation(StrEnum):
    LOCKED = "locked"
    SUSPENDED = "suspended"
    BANNED = "banned"


@dataclass(frozen=True)
class LockState:
    failures: int = 0
    level: int = 0
    locked_until: datetime | None = None
    banned: bool = False


def is_blocked(state: LockState, now: datetime) -> bool:
    return state.banned or (state.locked_until is not None and state.locked_until > now)


def after_failure(state: LockState, now: datetime) -> tuple[LockState, Escalation | None]:
    # Attempts while blocked are refused before they are checked, so they never count.
    if is_blocked(state, now):
        return state, None
    failures = state.failures + 1
    if failures < FAILURES_PER_STEP:
        return replace(state, failures=failures), None
    level = state.level + 1
    if level > len(STEPS):
        return LockState(level=level, banned=True), Escalation.BANNED
    escalation = Escalation.SUSPENDED if level == len(STEPS) else Escalation.LOCKED
    return LockState(level=level, locked_until=now + STEPS[level - 1]), escalation


def after_success(state: LockState) -> LockState:
    return LockState(banned=state.banned)
