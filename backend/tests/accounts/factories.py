from itertools import count
from typing import Any

from django.utils import timezone

from apps.accounts.models import User

PASSWORD = "Chai-At-Four-42"

_numbers = count()


def make_user(**fields: Any) -> User:
    number = next(_numbers)
    username = fields.pop("username", f"person{number}")
    values: dict[str, Any] = {
        "username": username,
        "email": f"{username}@example.com",
        "display_name": f"Person {number}",
        "email_verified_at": timezone.now(),
    } | fields
    return User.objects.create_user(password=PASSWORD, **values)
