from django.db import transaction
from django.db.models import Count, IntegerField, OuterRef, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce

from apps.chat import events
from apps.chat.models import Channel, ChannelMember, Message
from apps.core.unread import marker_after, unread_count
from apps.notifications import services as notifications


def with_read_state(channels: QuerySet[Channel], user_id: int) -> QuerySet[Channel]:
    """Annotate `last_read_seq` (None outside the channel) and `deleted_unread`."""
    mine = ChannelMember.objects.filter(channel=OuterRef("pk"), user_id=user_id)
    deleted = (
        Message.objects.filter(
            channel=OuterRef("pk"),
            seq__gt=OuterRef("last_read_seq"),
            deleted_at__isnull=False,
        )
        .order_by()
        .values("channel")
        .annotate(n=Count("pk"))
        .values("n")
    )
    return channels.annotate(last_read_seq=Subquery(mine.values("last_read_seq")[:1])).annotate(
        deleted_unread=Coalesce(Subquery(deleted, output_field=IntegerField()), Value(0))
    )


def unread_of(channel: Channel) -> int | None:
    """For a channel from with_read_state. None for someone outside it: they have no marker."""
    last_read: int | None = getattr(channel, "last_read_seq", None)
    if last_read is None:
        return None
    return unread_count(channel.last_seq, last_read, getattr(channel, "deleted_unread", 0))


def mark_read(channel: Channel, user_id: int, seq: int) -> int | None:
    """Move the person's marker forward to `seq`. Returns the marker, or None outside the channel.

    The update only matches a lower marker, so two devices reporting at once can't move it back.
    """
    member = (
        ChannelMember.objects.select_related("channel")
        .filter(channel=channel, user_id=user_id)
        .first()
    )
    if member is None:
        return None
    target = marker_after(member.last_read_seq, seq, member.channel.last_seq)
    with transaction.atomic():
        moved = ChannelMember.objects.filter(pk=member.pk, last_read_seq__lt=target).update(
            last_read_seq=target
        )
        if moved:
            events.read_moved(user_id, channel.pk, target)
            notifications.read_up_to(user_id, channel.pk, target)
            return target
    # Another device may have moved it further meanwhile.
    stored: int = (
        ChannelMember.objects.filter(pk=member.pk).values_list("last_read_seq", flat=True).get()
    )
    return stored
