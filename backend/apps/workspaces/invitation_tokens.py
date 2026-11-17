"""Invitation link tokens. Only the SHA-256 of a token is ever stored."""

import hashlib
import secrets

from apps.workspaces.models import Invitation


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(invitation: Invitation) -> str:
    """Give the invitation a fresh token, store only its hash, and return the token."""
    token = secrets.token_urlsafe(32)
    invitation.token_hash = hash_token(token)
    invitation.save(update_fields=["token_hash"])
    return token
