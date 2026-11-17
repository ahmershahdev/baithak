from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.lockout import Escalation, LockState, after_failure, after_success, is_blocked


def _state(user: User) -> LockState:
    return LockState(
        failures=user.failed_attempts,
        level=user.lock_level,
        locked_until=user.locked_until,
        banned=user.banned_at is not None,
    )


def _store(user: User, state: LockState) -> None:
    user.failed_attempts = state.failures
    user.lock_level = state.level
    user.locked_until = state.locked_until
    if state.banned and user.banned_at is None:
        user.banned_at = timezone.now()
    user.save(update_fields=["failed_attempts", "lock_level", "locked_until", "banned_at"])


def blocked(user: User) -> bool:
    return is_blocked(_state(user), timezone.now())


def record_failure(user: User) -> Escalation | None:
    """Count a wrong password or reset code, and tell the owner when the account climbs a step."""
    from apps.accounts.tasks import send_lockout_email

    with transaction.atomic():
        # Locked so two wrong attempts at the same moment both count.
        locked = User.objects.select_for_update().get(pk=user.pk)
        state, escalation = after_failure(_state(locked), timezone.now())
        _store(locked, state)
    # Sent once the new lock is committed, so the email never describes a lock that isn't there.
    if escalation is not None:
        send_lockout_email.delay(user.pk, escalation.value)
    return escalation


def record_success(user: User) -> None:
    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        _store(locked, after_success(_state(locked)))


def unlock(user: User) -> None:
    """For admins: lift any lock or ban and start the ladder again."""
    _store(user, LockState())
    user.banned_at = None
    user.save(update_fields=["banned_at"])
