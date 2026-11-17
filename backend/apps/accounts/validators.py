from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.core import passwords


class StrongPasswordValidator:
    """Django's validator interface around apps/core/passwords.py."""

    def validate(self, password: str, user: User | None = None) -> None:
        missing = passwords.missing(password)
        if missing:
            raise ValidationError(
                "Your password needs " + ", ".join(missing) + ".", code="password_too_weak"
            )

    def get_help_text(self) -> str:
        return "Use " + ", ".join(rule for rule, _ in passwords.RULES) + "."
