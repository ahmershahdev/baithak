import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import PasswordResetCode, User

CODE_MINUTES = 10
TRIES_PER_CODE = 3


def _digest(code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), code.encode(), hashlib.sha256).hexdigest()


def issue(user: User) -> str:
    """A new 6-digit code, valid for 10 minutes; any older code stops working."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = timezone.now()
    with transaction.atomic():
        PasswordResetCode.objects.filter(user=user, used_at=None).update(used_at=now)
        PasswordResetCode.objects.create(
            user=user, code_hash=_digest(code), expires_at=now + timedelta(minutes=CODE_MINUTES)
        )
    return code


def redeem(user: User, code: str) -> bool:
    """Use the code if it is the live one. Each code allows three tries, then it is spent."""
    now = timezone.now()
    with transaction.atomic():
        live = (
            PasswordResetCode.objects.select_for_update()
            .filter(user=user, used_at=None, expires_at__gt=now)
            .order_by("-created_at")
            .first()
        )
        if live is None:
            return False
        if hmac.compare_digest(live.code_hash, _digest(code)):
            live.used_at = now
            live.save(update_fields=["used_at"])
            return True
        live.attempts += 1
        if live.attempts >= TRIES_PER_CODE:
            live.used_at = now
        live.save(update_fields=["attempts", "used_at"])
        return False
