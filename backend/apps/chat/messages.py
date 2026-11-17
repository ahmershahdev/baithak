from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.chat import events
from apps.chat.models import Channel, Message


def _lock(channel: Channel) -> Channel:
    return Channel.objects.select_for_update().get(pk=channel.pk)


def post(channel: Channel, author: User, body: str, client_id: str = "") -> tuple[Message, bool]:
    """Save a message with the channel's next seq and event. Returns (message, created).

    A repeated client_id from the same author returns the stored message instead of a second
    copy, so a send retried after a dropped connection is not duplicated.
    """
    with transaction.atomic():
        locked = _lock(channel)
        if client_id:
            existing = Message.objects.filter(
                channel=locked, author=author, client_id=client_id
            ).first()
            if existing is not None:
                return existing, False
        locked.last_seq += 1
        locked.last_event += 1
        locked.save(update_fields=["last_seq", "last_event"])
        message = Message.objects.create(
            channel=locked,
            seq=locked.last_seq,
            event=locked.last_event,
            author=author,
            body=body,
            client_id=client_id,
        )
        events.message_changed(message)
    return message, True


def edit(message: Message, body: str) -> Message:
    with transaction.atomic():
        locked = _lock(message.channel)
        locked.last_event += 1
        locked.save(update_fields=["last_event"])
        message.body = body
        message.edited_at = timezone.now()
        message.event = locked.last_event
        message.save(update_fields=["body", "edited_at", "event"])
        events.message_changed(message)
    return message


def delete(message: Message) -> Message:
    """The row stays so threads and counts hold; only the text goes."""
    with transaction.atomic():
        locked = _lock(message.channel)
        locked.last_event += 1
        locked.save(update_fields=["last_event"])
        message.body = ""
        message.deleted_at = timezone.now()
        message.event = locked.last_event
        message.save(update_fields=["body", "deleted_at", "event"])
        events.message_changed(message)
    return message
