"""Live events. Each one is sent after its transaction commits, once, to a Channels group.

Saved first, then broadcast (AGENTS.md): a client that misses an event finds the change by
catching up with `?after_event=`.
"""

from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from apps.chat.models import Channel, Message
from apps.chat.serializers import ChannelEventSerializer, MessageSerializer


def channel_group(channel_id: int) -> str:
    return f"chat.channel.{channel_id}"


def user_group(user_id: int) -> str:
    return f"chat.user.{user_id}"


def workspace_group(workspace_id: int) -> str:
    """Every open socket in the workspace, for who is online."""
    return f"chat.workspace.{workspace_id}"


def _send(group: str, payload: dict[str, Any]) -> None:
    layer = get_channel_layer()
    if layer is not None:
        async_to_sync(layer.group_send)(group, payload)


def message_changed(message: Message) -> None:
    """A message was sent, edited or deleted. Call inside the transaction that changed it."""
    payload = {
        "type": "chat.message",
        "channel": message.channel_id,
        "event": message.event,
        "message": dict(MessageSerializer(message).data),
    }
    transaction.on_commit(lambda: _send(channel_group(message.channel_id), payload))


def channel_changed(channel: Channel) -> None:
    """Name, topic or archive state changed."""
    payload = {
        "type": "chat.channel",
        "channel": channel.pk,
        "data": dict(ChannelEventSerializer(channel).data),
    }
    transaction.on_commit(lambda: _send(channel_group(channel.pk), payload))


def read_moved(user_id: int, channel_id: int, last_read_seq: int) -> None:
    """Sent to every socket of the person, so all their devices agree on what is unread."""
    payload = {"type": "chat.read", "channel": channel_id, "last_read_seq": last_read_seq}
    transaction.on_commit(lambda: _send(user_group(user_id), payload))


def notifications_changed(user_id: int) -> None:
    """The person's notifications changed (one arrived, some were read): their tabs refetch."""
    transaction.on_commit(lambda: _send(user_group(user_id), {"type": "chat.notifications"}))


def access_changed(user_id: int) -> None:
    """The person joined, left or was added to or removed from something: their open sockets
    work out again which channels they may hear."""
    transaction.on_commit(lambda: _send(user_group(user_id), {"type": "chat.access"}))
