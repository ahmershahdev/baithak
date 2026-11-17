from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.accounts.models import User


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "baithak.accounts.EmailVerificationTokenGenerator"

    # The token stops working once the email is verified or changed, so a link is single use.
    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return f"{user.pk}{user.email}{user.email_verified_at}{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()
password_reset_token = PasswordResetTokenGenerator()


def encode_uid(user: User) -> str:
    return urlsafe_base64_encode(force_bytes(user.pk))


def user_from_uid(uid: str) -> User | None:
    try:
        pk = int(force_str(urlsafe_base64_decode(uid)))
    except (TypeError, ValueError, OverflowError):
        return None
    return User.objects.filter(pk=pk, is_active=True).first()
