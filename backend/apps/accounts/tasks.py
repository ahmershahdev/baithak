from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.utils import timezone

from apps.accounts import devices, reset_codes
from apps.accounts.models import ContactMessage, User
from apps.accounts.tokens import email_verification_token, encode_uid
from apps.accounts.two_step import codes_left

# Tasks take a user id and make the token themselves, so no token passes through the broker.
email_task = shared_task(autoretry_for=(SMTPException, OSError), retry_backoff=True, max_retries=5)

SIGN_OFF = f"\n\nBaithak\nHelp: {settings.SUPPORT_EMAIL}\n{settings.SITE_URL}"


def _active_user(user_id: int) -> User | None:
    return User.objects.filter(pk=user_id, is_active=True).first()


def _mail(user: User, subject: str, body: str) -> None:
    send_mail(subject, body + SIGN_OFF, None, [user.email])


@email_task
def send_verification_email(user_id: int) -> None:
    user = _active_user(user_id)
    if user is None or user.email_verified:
        return
    token = email_verification_token.make_token(user)
    link = f"{settings.FRONTEND_URL}/verify-email?uid={encode_uid(user)}&token={token}"
    _mail(
        user,
        "Confirm your email for Baithak",
        f"Open this link to confirm your email and sign in:\n\n{link}\n\n"
        "If you did not sign up for Baithak, you can ignore this email.",
    )


@email_task
def send_password_reset_email(user_id: int) -> None:
    user = _active_user(user_id)
    if user is None or user.banned_at is not None:
        return
    code = reset_codes.issue(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={encode_uid(user)}&code={code}"
    _mail(
        user,
        f"{code} is your Baithak reset code",
        f"Your code to choose a new password is:\n\n    {code}\n\n"
        f"It works once and expires in {reset_codes.CODE_MINUTES} minutes. You can also open "
        f"this link:\n\n{link}\n\n"
        "If you did not ask for this, ignore this email; your password stays the same.",
    )


@email_task
def send_account_exists_email(user_id: int) -> None:
    user = _active_user(user_id)
    if user is None:
        return
    _mail(
        user,
        "You already have a Baithak account",
        "Someone tried to sign up for Baithak with this email, which already has an account.\n\n"
        f"If it was you and you forgot your password, ask for a reset code at "
        f"{settings.FRONTEND_URL}/forgot-password.\n\nIf it was not you, you can ignore this "
        "email.",
    )


LOCKOUT_TEXT = {
    "locked": "We locked sign-in to your Baithak account for a while after several wrong "
    "passwords or reset codes in a row.",
    "suspended": "Your Baithak account is suspended for a week after repeated wrong passwords "
    "or reset codes, even after earlier locks.",
    "banned": "Your Baithak account is now closed to sign-in after repeated wrong passwords or "
    "reset codes. Only our support team can open it again.",
}


@email_task
def send_lockout_email(user_id: int, escalation: str) -> None:
    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return
    until = (
        f"\n\nYou can try again after {user.locked_until:%d %b %Y, %H:%M} UTC."
        if user.locked_until
        else ""
    )
    _mail(
        user,
        "Someone is trying to get into your Baithak account",
        f"{LOCKOUT_TEXT[escalation]}{until}\n\n"
        "If this was you, wait and try again, or reset your password once the lock ends. If it "
        f"was not you, your password is still safe, but tell us at {settings.SUPPORT_EMAIL} and "
        "change it once you can sign in.",
    )


@email_task
def send_password_changed_email(user_id: int) -> None:
    user = _active_user(user_id)
    if user is None:
        return
    _mail(
        user,
        "Your Baithak password was changed",
        f"The password for {user.email} was changed at {timezone.now():%d %b %Y, %H:%M} UTC, "
        "and every other device was signed out.\n\n"
        f"If you did not do this, write to {settings.SUPPORT_EMAIL} right away.",
    )


@email_task
def send_contact_message(message_id: int) -> None:
    message = ContactMessage.objects.filter(pk=message_id, sent_at=None).first()
    if message is None:
        return
    EmailMessage(
        subject=f"Contact form: {message.name}",
        body=f"From: {message.name} <{message.email}>\n\n{message.message}",
        to=[settings.SUPPORT_EMAIL],
        reply_to=[message.email],
    ).send()
    message.sent_at = timezone.now()
    message.save(update_fields=["sent_at"])


TWO_STEP_TEXT = {
    "on": (
        "Two-step sign-in is on",
        "Two-step sign-in was turned on for {email}. From now on, signing in asks for a code "
        "from your authenticator app after your password.",
    ),
    "off": (
        "Two-step sign-in is off",
        "Two-step sign-in was turned off for {email}. Signing in now needs only your password.",
    ),
    "codes": (
        "New recovery codes for Baithak",
        "New recovery codes were made for {email}. The old ones no longer work.",
    ),
    "recovery": (
        "A recovery code was used to sign in to Baithak",
        "Someone signed in to {email} with a recovery code instead of the authenticator app. "
        "Each code works once; you have {left} left.",
    ),
}


@email_task
def send_two_step_email(user_id: int, kind: str) -> None:
    user = _active_user(user_id)
    if user is None:
        return
    subject, text = TWO_STEP_TEXT[kind]
    _mail(
        user,
        subject,
        f"{text.format(email=user.email, left=codes_left(user))} "
        f"({timezone.now():%d %b %Y, %H:%M} UTC)\n\n"
        f"If this was not you, reset your password and write to {settings.SUPPORT_EMAIL} right "
        "away.",
    )


@shared_task
def prune_devices() -> None:
    devices.prune()
