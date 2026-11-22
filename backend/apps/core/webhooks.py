"""Incoming webhooks: the URL is the only secret, so only a digest of its token is stored."""

import hashlib
import secrets


def new_token() -> str:
    return secrets.token_urlsafe(32)


def digest(token: str) -> str:
    """What is stored and looked up. A database leak then gives nobody a working URL; a plain
    SHA-256 is enough because the token is random, not a password."""
    return hashlib.sha256(token.encode()).hexdigest()
