"""Two-step sign-in: an authenticator app's codes (apps/core/totp.py), with recovery codes for
when the phone is lost. Rules for when it is asked are in docs/architecture.md, Accounts."""

import hashlib
import hmac
import time
from enum import StrEnum

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RecoveryCode, TwoStep, User
from apps.core import totp
from apps.files import crypto


class Used(StrEnum):
    APP = "app"
    RECOVERY = "recovery"


def _digest(code: str) -> str:
    message = f"recovery:{totp.normal_recovery_code(code)}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _secret(row: TwoStep) -> str:
    return crypto.unseal(bytes(row.secret)).decode()


def is_on(user: User) -> bool:
    return TwoStep.objects.filter(user=user, enabled_at__isnull=False).exists()


def codes_left(user: User) -> int:
    return RecoveryCode.objects.filter(user=user, used_at=None).count()


def start(user: User) -> tuple[str, str]:
    """A new key for the person to add to their app. Nothing changes at sign-in until `confirm`."""
    secret = totp.new_secret()
    with transaction.atomic():
        TwoStep.objects.filter(user=user, enabled_at=None).delete()
        TwoStep.objects.create(user=user, secret=crypto.seal(secret.encode()))
    return secret, totp.setup_uri(secret, user.email)


def _new_codes(user: User) -> list[str]:
    codes = totp.new_recovery_codes()
    RecoveryCode.objects.filter(user=user).delete()
    RecoveryCode.objects.bulk_create(RecoveryCode(user=user, code_hash=_digest(c)) for c in codes)
    return codes


def confirm(user: User, code: str) -> list[str] | None:
    """Turns two-step sign-in on if the code is right; returns the new recovery codes."""
    with transaction.atomic():
        row = TwoStep.objects.select_for_update().filter(user=user, enabled_at=None).first()
        if row is None:
            return None
        step = totp.match(_secret(row), code, time.time(), None)
        if step is None:
            return None
        row.last_step = step
        row.enabled_at = timezone.now()
        row.save(update_fields=["last_step", "enabled_at"])
        return _new_codes(user)


def check(user: User, code: str) -> Used | None:
    """Whether a code from the app, or an unused recovery code, is right. Each works once."""
    with transaction.atomic():
        # Locked so two sign-ins with the same code at the same moment can't both pass.
        row = (
            TwoStep.objects.select_for_update().filter(user=user, enabled_at__isnull=False).first()
        )
        if row is None:
            return None
        step = totp.match(_secret(row), code, time.time(), row.last_step)
        if step is not None:
            row.last_step = step
            row.save(update_fields=["last_step"])
            return Used.APP
        spent = RecoveryCode.objects.filter(
            user=user, code_hash=_digest(code), used_at=None
        ).update(used_at=timezone.now())
        return Used.RECOVERY if spent else None


def new_codes(user: User) -> list[str]:
    with transaction.atomic():
        return _new_codes(user)


def turn_off(user: User) -> None:
    with transaction.atomic():
        TwoStep.objects.filter(user=user).delete()
        RecoveryCode.objects.filter(user=user).delete()
