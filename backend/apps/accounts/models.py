from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

# The handle is what people type after @, so it keeps to characters a mention can end on.
username_validator = RegexValidator(
    r"^[a-z0-9][a-z0-9_.-]{1,29}$",
    "Use 2 to 30 lowercase letters, digits, dots, hyphens or underscores, starting with a letter "
    "or digit.",
)


class User(AbstractUser):
    username = models.CharField(max_length=30, unique=True, validators=[username_validator])
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=80, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["username"]

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None
