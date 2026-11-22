from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.chat import events
from apps.chat.models import ChannelMember, Message
from apps.core.channels import CONVERSATIONS
from apps.core.notifications import Kind, assignee_to_tell, recipients
from apps.issues.models import Issue
from apps.notifications.models import Notification


def notify(message: Message) -> None:
    """Tell the people a message is for. Safe to call again after an edit: only people not
    told about this message yet are told. Call inside the message's transaction."""
    channel = message.channel
    conversation = channel.kind in CONVERSATIONS
    members: list[int] = []
    if conversation or message.mentions_channel:
        members = list(
            ChannelMember.objects.filter(channel=channel).values_list("user_id", flat=True)
        )
    found = recipients(
        author_id=message.author_id,
        mentioned=message.mentions.values_list("pk", flat=True),
        channel_wide=message.mentions_channel,
        members=members,
        conversation=conversation,
    )
    told = set(Notification.objects.filter(message=message).values_list("user_id", flat=True))
    new = [
        Notification(
            workspace_id=channel.workspace_id,
            user_id=user_id,
            kind=kind,
            channel=channel,
            message=message,
        )
        for user_id, kind in found.items()
        if user_id not in told
    ]
    Notification.objects.bulk_create(new, ignore_conflicts=True)
    for item in new:
        events.notifications_changed(item.user_id)


def issue_assigned(issue: Issue, actor: User, before: int | None) -> None:
    """Tell the new assignee; a previous one who hasn't read theirs yet loses it, since the issue
    is no longer theirs. Call inside the issue's transaction."""
    if before is not None and before != issue.assignee_id:
        stale = Notification.objects.filter(
            issue=issue, user_id=before, kind=Kind.ASSIGNED, read_at__isnull=True
        )
        if stale.delete()[0]:
            events.notifications_changed(before)
    user_id = assignee_to_tell(actor_id=actor.pk, before=before, after=issue.assignee_id)
    if user_id is None:
        return
    Notification.objects.create(
        workspace_id=issue.workspace_id,
        user_id=user_id,
        kind=Kind.ASSIGNED,
        issue=issue,
        actor=actor,
    )
    events.notifications_changed(user_id)


def read_up_to(user_id: int, channel_id: int, seq: int) -> None:
    """The person read the channel up to `seq`, so its notifications up to there are read."""
    with transaction.atomic():
        changed = Notification.objects.filter(
            user_id=user_id,
            channel_id=channel_id,
            read_at__isnull=True,
            message__seq__lte=seq,
        ).update(read_at=timezone.now())
        if changed:
            events.notifications_changed(user_id)
