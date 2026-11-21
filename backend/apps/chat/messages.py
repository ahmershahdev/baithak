from collections.abc import Sequence

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.chat import events, mentions
from apps.chat.models import Channel, ChannelMember, Message, Reaction
from apps.core.reactions import can_add
from apps.files import storage
from apps.files.models import Attachment
from apps.notifications import services as notifications
from apps.notifications.models import Notification


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
    attachment_ids: Sequence[int] = (),
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
        named, everyone = mentions.resolve(locked, author.pk, body)
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
            mentions_channel=everyone,
        )
        message.mentions.set(named)
        if attachment_ids:
            # Only the author's own files, not yet sent, still in this channel; a second send
            # racing for the same file finds it taken and rolls back.
            taken = Attachment.objects.filter(
                pk__in=attachment_ids, channel=locked, uploader=author, message__isnull=True
            ).update(message=message)
            if taken != len(set(attachment_ids)):
                raise FilesUnavailable
        events.message_changed(message)
        notifications.notify(message)
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
            notifications.read_up_to(author.pk, locked.pk, seq)
    return message, True


def edit(message: Message, body: str) -> Message:
    with transaction.atomic():
        locked = _lock(message.channel)
        locked.last_event += 1
        locked.save(update_fields=["last_event"])
        message.body = body
        message.edited_at = timezone.now()
        message.event = locked.last_event
        named, message.mentions_channel = mentions.resolve(locked, message.author_id, body)
        message.save(update_fields=["body", "edited_at", "event", "mentions_channel"])
        message.mentions.set(named)
        # People newly named in the edit are told; nobody is told twice.
        notifications.notify(message)
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
        message.mentions_channel = False
        message.save(update_fields=["body", "deleted_at", "event", "mentions_channel"])
        message.mentions.clear()
        message.reactions.all().delete()
        Notification.objects.filter(message=message).delete()
        attached = Attachment.objects.filter(message=message)
        keys = [key for f in attached for key in (f.storage_key, f.preview_key) if key]
        attached.delete()

        def remove_files() -> None:
            for key in keys:
                storage.delete(key)

        # Only once the rows are gone for good; a rolled-back delete keeps its files.
        transaction.on_commit(remove_files)
        events.message_changed(message)
    return message


class TooManyReactions(Exception):
    pass


class FilesUnavailable(Exception):
    """An attachment isn't the author's to send here, or another message took it."""


def touch(message: Message) -> Message:
    """Give a message a new event without changing its text: something attached to it changed
    (an image preview is ready), and open sockets and catch-up should hear."""
    with transaction.atomic():
        locked = _lock(message.channel)
        locked.last_event += 1
        locked.save(update_fields=["last_event"])
        message.event = locked.last_event
        message.save(update_fields=["event"])
        events.message_changed(message)
    return message


def react(message: Message, user: User, emoji: str, *, on: bool) -> Message:
    """Add or take back one person's emoji. A change gives the message a new event, so it
    reaches open sockets and catch-up like an edit."""
    with transaction.atomic():
        locked = _lock(message.channel)
        mine = Reaction.objects.filter(message=message, user=user, emoji=emoji)
        if on:
            if mine.exists():
                return message
            emoji_here = set(message.reactions.values_list("emoji", flat=True))
            if not can_add(len(emoji_here), present=emoji in emoji_here):
                raise TooManyReactions
            Reaction.objects.create(message=message, user=user, emoji=emoji)
        elif not mine.delete()[0]:
            return message
        locked.last_event += 1
        locked.save(update_fields=["last_event"])
        message.event = locked.last_event
        message.save(update_fields=["event"])
        events.message_changed(message)
    return message
