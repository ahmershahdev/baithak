import hashlib
from typing import Any

from django.conf import settings
from django.core.cache import cache

# Bots fill every field they find; people never see this one (it is hidden on the page).
HONEYPOT_FIELD = "website"


def caught_by_honeypot(data: Any) -> bool:
    return bool(data.get(HONEYPOT_FIELD))


def _failures_key(email: str) -> str:
    # Hashed so the cache never holds a list of email addresses.
    return "signin-failures:" + hashlib.sha256(email.encode()).hexdigest()


def account_locked(email: str) -> bool:
    return int(cache.get(_failures_key(email), 0)) >= settings.SIGNIN_MAX_FAILURES


def note_failure(email: str) -> None:
    key = _failures_key(email)
    # add() only sets the expiry on the first failure, so the window starts there and a steady
    # trickle of guesses can't keep extending it forever.
    cache.add(key, 0, timeout=settings.SIGNIN_LOCKOUT_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=settings.SIGNIN_LOCKOUT_SECONDS)


def clear_failures(email: str) -> None:
    cache.delete(_failures_key(email))


def allow_reset_request(email: str, per_hour: int = 3) -> bool:
    key = "reset-requests:" + hashlib.sha256(email.encode()).hexdigest()
    cache.add(key, 0, timeout=3600)
    try:
        return cache.incr(key) <= per_hour
    except ValueError:
        cache.set(key, 1, timeout=3600)
        return True
