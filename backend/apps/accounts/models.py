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
    # Emails about unread mentions and direct messages (apps/notifications/tasks.py).
    notify_by_email = models.BooleanField(default=True)
    quiet_start = models.TimeField(null=True, blank=True)
    quiet_end = models.TimeField(null=True, blank=True)
    time_zone = models.CharField(max_length=64, default="UTC")

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


class TwoStep(models.Model):
    """Two-step sign-in with an authenticator app. A row with no `enabled_at` is a setup the
    person started but hasn't confirmed with a code; it does nothing at sign-in."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="two_step")
    # The base32 key, sealed with ENCRYPTION_KEYS (apps/files/crypto.py).
    secret = models.BinaryField()
    # The newest 30-second step a code was used for; older and equal steps are refused.
    last_step = models.BigIntegerField(null=True, blank=True)
    enabled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"two-step sign-in for {self.user_id}"


class RecoveryCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    # HMAC with the secret key, like reset codes.
    code_hash = models.CharField(max_length=64)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"recovery code for {self.user_id}"


class Device(models.Model):
    """One signed-in session. The session holds this row's id; deleting the row signs that
    session out on its next request (apps/accounts/devices.py)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"device {self.pk} of {self.user_id}"
