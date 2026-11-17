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
    # The lockout ladder (apps/core/lockout.py), kept on the account so it survives restarts and
    # an admin can see and lift it.
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    lock_level = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = ["username"]

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


class PasswordResetCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_codes")
    # HMAC of the 6-digit code with the secret key: a copied table can't be brute-forced
    # without the key, where a plain hash of a million possible codes could.
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"reset code for {self.user_id}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=80)
    email = models.EmailField()
    message = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"
