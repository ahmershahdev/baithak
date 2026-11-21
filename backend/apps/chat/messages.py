from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.chat import events
from apps.chat.models import Channel, ChannelMember, Message


def _lock(channel: Channel) -> Channel:
    return Channel.objects.select_for_update().get(pk=channel.pk)


def post(
    channel: Channel,
    author: User,
    body: str,
    client_id: str = "",
    *,
    parent: Message | None = None,
    also_in_channel: bool = False,
) -> tuple[Message, bool]:
    """Save a message, or a reply to `parent`, with the channel's next event. Returns
    (message, created).

    A message takes the next seq; a reply takes one only when also sent to the channel. A reply
    also gives the parent a new event carrying its reply count, so catching up by event brings
    thread changes too. A repeated client_id from the same author returns the stored message,
    so a send retried after a dropped connection is not duplicated.
    """
    with transaction.atomic():
        locked = _lock(channel)
        if client_id:
            existing = (
                Message.objects.filter(channel=locked, author=author, client_id=client_id)
                .select_related("parent")
                .first()
            )
            if existing is not None:
                return existing, False
        seq = None
        if parent is None or also_in_channel:
            locked.last_seq += 1
            seq = locked.last_seq
        locked.last_event += 1
        thread_seq = None
        if parent is not None:
            # Fresh under the channel lock: reply_count numbers the replies.
            parent = Message.objects.get(pk=parent.pk)
            thread_seq = parent.reply_count + 1
        message = Message.objects.create(
            channel=locked,
            seq=seq,
            event=locked.last_event,
            parent=parent,
            thread_seq=thread_seq,
            also_in_channel=parent is not None and also_in_channel,
            author=author,
            body=body,
            client_id=client_id,
        )
        events.message_changed(message)
        if parent is not None:
            locked.last_event += 1
            parent.reply_count = message.thread_seq or 0
            parent.last_reply_at = message.created_at
            parent.event = locked.last_event
            parent.save(update_fields=["reply_count", "last_reply_at", "event"])
            events.message_changed(parent)
        locked.save(update_fields=["last_seq", "last_event"])
        # Posting means the author has seen the channel up to here.
        if seq is not None and ChannelMember.objects.filter(
            channel=locked, user=author, last_read_seq__lt=seq
        ).update(last_read_seq=seq):
            events.read_moved(author.pk, locked.pk, seq)
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
