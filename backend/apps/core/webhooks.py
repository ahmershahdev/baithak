"""Webhook tokens and how deliveries are retried.

An incoming webhook's URL is its only secret, so only a digest of its token is stored.
"""

import hashlib
import secrets

# A delivery that keeps failing is tried this many times in all, then marked failed.
MAX_ATTEMPTS = 6
# Finished deliveries are kept this long, for the log.
KEEP_DAYS = 30


def new_token() -> str:
    return secrets.token_urlsafe(32)


def digest(token: str) -> str:
    """What is stored and looked up. A database leak then gives nobody a working URL; a plain
    SHA-256 is enough because the token is random, not a password."""
    return hashlib.sha256(token.encode()).hexdigest()


def retry_delay(failures: int) -> int:
    """Seconds before the next try after `failures` failed ones: 30 s, 1 min, 2, 4, 8, at most
    an hour, so a short outage is ridden out and a long one doesn't hammer the database."""
    return int(min(30 * 2 ** (failures - 1), 3600))


def gives_up(attempts: int) -> bool:
    return attempts >= MAX_ATTEMPTS
