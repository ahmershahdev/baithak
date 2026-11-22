"""Emails about mentions and direct messages left unread.

The beat runs email_unread every few minutes; each person gets one email for what piled up,
outside their quiet hours, and only while they aren't online in that workspace.
"""

import asyncio
from collections import defaultdict
from datetime import datetime
from smtplib import SMTPException
from typing import cast
from zoneinfo import ZoneInfo

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.chat import presence
from apps.chat.access import readable_channels
from apps.chat.models import Channel, Message
from apps.core.channels import ChannelKind
from apps.core.notifications import EMAIL_AFTER, EMAILED_KINDS, Kind, in_quiet_hours
from apps.notifications.models import Notification
from apps.workspaces.models import Member, Workspace

MAX_LISTED = 10
PREVIEW = 160


def _pending(now: datetime) -> QuerySet[Notification]:
    return Notification.objects.filter(
        read_at__isnull=True,
        emailed_at__isnull=True,
        created_at__lte=now - EMAIL_AFTER,
        kind__in=list(EMAILED_KINDS),
        user__is_active=True,
        user__notify_by_email=True,
        user__email_verified_at__isnull=False,
    )


@shared_task
def email_unread() -> None:
    for user_id in _pending(timezone.now()).values_list("user_id", flat=True).distinct():
        email_person.delay(user_id)


def _quiet_now(user: User, now: datetime) -> bool:
    local = now.astimezone(ZoneInfo(user.time_zone)).time()
    return in_quiet_hours(local, user.quiet_start, user.quiet_end)


def _sendable(user: User, notifications: list[Notification]) -> list[Notification]:
    """Keep what the person can still read, in workspaces they are not online in now."""
    keep: list[Notification] = []
    by_workspace: dict[int, list[Notification]] = defaultdict(list)
    for item in notifications:
        by_workspace[item.workspace_id].append(item)
    for workspace_id, items in by_workspace.items():
        member = (
            Member.objects.select_related("workspace")
            .filter(workspace_id=workspace_id, user=user)
            .first()
        )
        if member is None or user.pk in asyncio.run(presence.online_users(workspace_id)):
            continue
        readable = set(readable_channels(member).values_list("pk", flat=True))
        keep.extend(item for item in items if item.channel_id in readable)
    return keep


def _about(item: Notification) -> tuple[Channel, Message]:
    # Every emailed kind is about a message, so both are set (EMAILED_KINDS).
    return cast(Channel, item.channel), cast(Message, item.message)


def _where(item: Notification) -> str:
    channel, _ = _about(item)
    if channel.kind == ChannelKind.DIRECT:
        return "a direct message"
    if channel.kind == ChannelKind.GROUP:
        return "a group conversation"
    return f"#{channel.name}"


def _line(item: Notification) -> str:
    _, message = _about(item)
    author = message.author
    name = (author.display_name or author.username) if author else "Someone"
    text = " ".join(message.body.split()) or "(a file)"
    if len(text) > PREVIEW:
        text = text[: PREVIEW - 3].rstrip() + "..."
    verb = "mentioned you" if item.kind == Kind.MENTION else "wrote to you"
    return f"{name} {verb} in {_where(item)}:\n  {text}"


def _compose(items: list[Notification]) -> tuple[str, str]:
    workspaces: dict[int, Workspace] = {item.workspace_id: item.workspace for item in items}
    first = items[0]
    if len(items) == 1:
        author = _about(first)[1].author
        name = (author.display_name or author.username) if author else "Someone"
        verb = "mentioned you" if first.kind == Kind.MENTION else "wrote to you"
        subject = f"{name} {verb} in {first.workspace.name}"
    elif len(workspaces) == 1:
        subject = f"{len(items)} unread messages for you in {first.workspace.name}"
    else:
        subject = f"{len(items)} unread messages for you on Baithak"
    lines = [_line(item) for item in items[:MAX_LISTED]]
    if len(items) > MAX_LISTED:
        lines.append(f"...and {len(items) - MAX_LISTED} more.")
    links = [
        f"{settings.FRONTEND_URL}/w/{workspace.slug}/notifications"
        for workspace in workspaces.values()
    ]
    body = (
        "\n\n".join(lines)
        + "\n\nRead them in Baithak:\n"
        + "\n".join(links)
        + "\n\nTurn these emails off or set quiet hours in your settings:\n"
        + f"{settings.FRONTEND_URL}/w/{first.workspace.slug}/me"
        + f"\n\nBaithak\nHelp: {settings.SUPPORT_EMAIL}"
    )
    return subject, body


@shared_task(autoretry_for=(SMTPException, OSError), retry_backoff=True, max_retries=5)
def email_person(user_id: int) -> None:
    user = User.objects.filter(pk=user_id).first()
    now = timezone.now()
    if user is None or _quiet_now(user, now):
        # Still unread after quiet hours end, so a later run sends it.
        return
    found = list(
        _pending(now)
        .filter(user=user)
        .select_related("workspace", "channel", "message__author")
        .order_by("created_at")
    )
    items = _sendable(user, found)
    if not items:
        return
    # Claim them first so two runs can't both send; give them back if the mail fails.
    ids = [item.pk for item in items]
    if not Notification.objects.filter(pk__in=ids, emailed_at__isnull=True).update(emailed_at=now):
        return
    subject, body = _compose(items)
    try:
        send_mail(subject, body, None, [user.email])
    except (SMTPException, OSError):
        Notification.objects.filter(pk__in=ids, emailed_at=now).update(emailed_at=None)
        raise
