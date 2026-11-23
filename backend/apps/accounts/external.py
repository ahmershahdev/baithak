"""Which Baithak account a provider's sign-in belongs to: linked before, the same verified
email, or a new account."""

import secrets
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts import devices, lockout
from apps.accounts.models import ExternalIdentity, User
from apps.accounts.serializers import check_handle
from apps.core import handles


class NotAllowed(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _free_handle(email: str) -> str:
    base = handles.from_email(email)
    if check_handle(base) is None:
        return base
    for _ in range(20):
        candidate = f"{base[:24]}{secrets.randbelow(10_000)}"
        if check_handle(candidate) is None:
            return candidate
    return f"member{secrets.token_hex(4)}"


def account_for(provider: str, claims: dict[str, Any]) -> User:
    """The person to sign in. Raises NotAllowed with a short reason code otherwise."""
    subject = str(claims["sub"])
    linked = (
        ExternalIdentity.objects.select_related("user")
        .filter(provider=provider, subject=subject)
        .first()
    )
    if linked:
        user = linked.user
    else:
        try:
            user = _link(provider, subject, claims)
        except IntegrityError:
            # A second sign-in with the same account linked it first; use that link.
            user = ExternalIdentity.objects.get(provider=provider, subject=subject).user
    if not user.is_active:
        raise NotAllowed("inactive")
    if lockout.blocked(user):
        raise NotAllowed("locked")
    return user


def _link(provider: str, subject: str, claims: dict[str, Any]) -> User:
    email = str(claims.get("email", "")).strip().lower()
    # Only an address the provider itself has verified may match or create an account.
    if not email or claims.get("email_verified") is not True:
        raise NotAllowed("unverified")
    with transaction.atomic():
        user = User.objects.select_for_update().filter(email=email).first()
        if user is None:
            user = _create(email, str(claims.get("name", ""))[:80])
        elif not user.email_verified:
            # Anyone could have signed up with this address without owning it. The provider
            # proves who owns it, so the unproven password and its sessions stop working.
            user.set_unusable_password()
            user.email_verified_at = timezone.now()
            user.save(update_fields=["password", "email_verified_at"])
            devices.end_all(user)
        ExternalIdentity.objects.create(user=user, provider=provider, subject=subject, email=email)
    return user


def _create(email: str, name: str) -> User:
    for _ in range(3):
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    username=_free_handle(email),
                    display_name=name,
                    password=None,
                    email_verified_at=timezone.now(),
                )
                return user
        except IntegrityError:
            # Another sign-up took the handle between the check and the insert; pick again.
            continue
    raise NotAllowed("failed")
