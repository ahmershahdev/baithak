from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import User
from apps.accounts.tokens import email_verification_token, encode_uid, password_reset_token

# Tasks take a user id and make the token themselves, so no token passes through the broker.
# A failed send (Resend down, timeout) is retried with backoff; a retry builds a fresh token.
email_task = shared_task(autoretry_for=(SMTPException, OSError), retry_backoff=True, max_retries=5)


def _link(path: str, user: User, token: str) -> str:
    return f"{settings.FRONTEND_URL}{path}?uid={encode_uid(user)}&token={token}"


def _active_user(user_id: int) -> User | None:
    return User.objects.filter(pk=user_id, is_active=True).first()


@email_task
def send_verification_email(user_id: int) -> None:
    user = _active_user(user_id)
    if user is None or user.email_verified:
        return
    link = _link("/verify-email", user, email_verification_token.make_token(user))
    send_mail(
        "Confirm your email for Baithak",
        f"Open this link to confirm your email and sign in:\n\n{link}\n\n"
        "If you did not sign up for Baithak, you can ignore this email.",
        None,
        [user.email],
    )


@email_task
def send_password_reset_email(user_id: int) -> None:
    user = _active_user(user_id)
    if user is None:
        return
    link = _link("/reset-password", user, password_reset_token.make_token(user))
    send_mail(
        "Reset your Baithak password",
        f"Open this link to choose a new password:\n\n{link}\n\n"
        "If you did not ask for this, you can ignore this email; your password stays the same.",
        None,
        [user.email],
    )


@email_task
def send_account_exists_email(user_id: int) -> None:
    user = _active_user(user_id)
    if user is None:
        return
    link = _link("/reset-password", user, password_reset_token.make_token(user))
    send_mail(
        "You already have a Baithak account",
        "Someone tried to sign up for Baithak with this email, which already has an account.\n\n"
        f"If it was you and you forgot your password, open this link to choose a new one:\n\n"
        f"{link}\n\nIf it was not you, you can ignore this email.",
        None,
        [user.email],
    )
