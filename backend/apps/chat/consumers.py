import asyncio
import time
import weakref
from dataclasses import dataclass
from typing import Any, cast

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.accounts.devices import SESSION_KEY as DEVICE_KEY
from apps.accounts.models import Device, User
from apps.chat import presence
from apps.chat.access import readable_channels
from apps.chat.events import channel_group, user_group, workspace_group
from apps.core.presence import typing_due
from apps.workspaces.models import Member

# Close codes in the 4000 range are free for applications (RFC 6455, 7.4.2).
NOT_SIGNED_IN = 4401
NOT_A_MEMBER = 4404


# How long join and leave announcements gather before they go out together.
PRESENCE_BATCH_SECONDS = 1.0


class PresenceBatcher:
    """Join and leave announcements, gathered per workspace and sent as one message.

    Sent one by one, N people arriving at once (a server restart, the morning) meant N x N
    messages, and the channel layer drops whatever is past each socket's queue of 100, so most
    were lost and online dots went wrong. Gathered, each socket gets about one per second.
    Pending changes are kept per event loop: tests run each in a loop of its own.
    """

    def __init__(self) -> None:
        self._pending: weakref.WeakKeyDictionary[
            asyncio.AbstractEventLoop, dict[int, dict[int, bool]]
        ] = weakref.WeakKeyDictionary()

    def add(self, layer: Any, workspace_id: int, user_id: int, *, online: bool) -> None:
        loop = asyncio.get_running_loop()
        pending = self._pending.setdefault(loop, {})
        changes = pending.get(workspace_id)
        if changes is None:
            changes = pending[workspace_id] = {}
            loop.call_later(
                PRESENCE_BATCH_SECONDS,
                lambda: loop.create_task(self._flush(layer, pending, workspace_id)),
            )
        # Gone and back within the batch: only the latest state goes out.
        changes[user_id] = online

    async def _flush(
        self, layer: Any, pending: dict[int, dict[int, bool]], workspace_id: int
    ) -> None:
        changes = pending.pop(workspace_id, {})
        if changes:
            await layer.group_send(
                workspace_group(workspace_id),
                {
                    "type": "chat.presence",
                    # Pairs, not a dict: the channel layer's msgpack wants string keys.
                    "changes": [[user, online] for user, online in changes.items()],
                },
            )


presence_batches = PresenceBatcher()


@dataclass(frozen=True)
class Readable:
    workspace_id: int
    channels: set[int]
    joined: set[int]


class WorkspaceConsumer(AsyncJsonWebsocketConsumer):
    """One socket per open workspace tab. It hears every channel the person may read, and who in
    the workspace is online.

    Which channels that is comes from readable_channels, the same rule as the REST API, worked
    out on connect and again whenever the person's access changes.
    """

    user_id: int
    device_id: int | None
    slug: str
    workspace_id: int
    subscribed: set[int]
    joined: set[int]
    person: dict[str, Any]
    typing_sent: dict[tuple[int, int | None], float]

    async def connect(self) -> None:
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=NOT_SIGNED_IN)
            return
        account = cast(User, user)
        self.user_id = account.pk
        self.device_id, signed_in = await self._device()
        if not signed_in:
            await self.close(code=NOT_SIGNED_IN)
            return
        self.person = {
            "id": account.pk,
            "username": account.username,
            "display_name": account.display_name,
        }
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.subscribed = set()
        self.joined = set()
        self.typing_sent = {}
        readable = await self._readable()
        if readable is None:
            await self.close(code=NOT_A_MEMBER)
            return
        self.workspace_id = readable.workspace_id
        await self.accept()
        await self.channel_layer.group_add(user_group(self.user_id), self.channel_name)
        await self.channel_layer.group_add(workspace_group(self.workspace_id), self.channel_name)
        await self._subscribe(readable)
        if await presence.connect(self.workspace_id, self.user_id, self.channel_name):
            await self._announce(online=True)
        online = await presence.online_users(self.workspace_id)
        await self.send_json({"type": "presence", "online": sorted(online)})

    async def disconnect(self, code: int) -> None:
        if not hasattr(self, "workspace_id"):
            return
        for channel_id in self.subscribed:
            await self.channel_layer.group_discard(channel_group(channel_id), self.channel_name)
        await self.channel_layer.group_discard(user_group(self.user_id), self.channel_name)
        await self.channel_layer.group_discard(
            workspace_group(self.workspace_id), self.channel_name
        )
        if await presence.disconnect(self.workspace_id, self.user_id, self.channel_name):
            await self._announce(online=False)

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        # The client sends little: pings, which also keep the person online, and typing notices.
        # Messages go through the REST API, so they are saved before anyone hears them.
        if not isinstance(content, dict):
            return
        if content.get("type") == "ping":
            await presence.refresh(self.workspace_id, self.user_id, self.channel_name)
            await self.send_json({"type": "pong"})
        elif content.get("type") == "typing":
            await self._typing(content.get("channel"), content.get("thread"))

    async def _typing(self, channel: object, thread: object) -> None:
        # Only where the person could post, and not more often than TYPING_EVERY per place.
        if type(channel) is not int or channel not in self.joined:
            return
        if thread is not None and type(thread) is not int:
            return
        place = (channel, thread)
        now = time.monotonic()
        if not typing_due(self.typing_sent.get(place), now):
            return
        self.typing_sent[place] = now
        await self.channel_layer.group_send(
            channel_group(channel),
            {"type": "chat.typing", "channel": channel, "thread": thread, "user": self.person},
        )

    async def _announce(self, *, online: bool) -> None:
        presence_batches.add(self.channel_layer, self.workspace_id, self.user_id, online=online)

    @database_sync_to_async
    def _device(self) -> tuple[int | None, bool]:
        """This session's device and whether it is still signed in. A session from before
        devices existed has none yet; it gets one on its next HTTP request."""
        session = self.scope.get("session")
        device_id = session.get(DEVICE_KEY) if session is not None else None
        if device_id is None:
            return None, True
        return device_id, Device.objects.filter(pk=device_id, user_id=self.user_id).exists()

    @database_sync_to_async
    def _readable(self) -> Readable | None:
        member = (
            Member.objects.select_related("workspace")
            .filter(workspace__slug=self.slug, user_id=self.user_id)
            .first()
        )
        if member is None:
            return None
        rows = list(readable_channels(member).only("pk", "archived_at"))
        return Readable(
            workspace_id=member.workspace_id,
            channels={channel.pk for channel in rows},
            joined={
                channel.pk
                for channel in rows
                if getattr(channel, "is_member", False) and channel.archived_at is None
            },
        )

    async def _subscribe(self, readable: Readable) -> None:
        channels = readable.channels
        for channel_id in channels - self.subscribed:
            await self.channel_layer.group_add(channel_group(channel_id), self.channel_name)
        for channel_id in self.subscribed - channels:
            await self.channel_layer.group_discard(channel_group(channel_id), self.channel_name)
        self.subscribed = channels
        self.joined = readable.joined
        await self.send_json({"type": "subscribed", "channels": sorted(channels)})

    async def chat_message(self, event: dict[str, Any]) -> None:
        # A group discard can race an event already queued for this socket.
        if event["channel"] in self.subscribed:
            await self.send_json(
                {
                    "type": "message",
                    "channel": event["channel"],
                    "event": event["event"],
                    "message": event["message"],
                }
            )

    async def chat_channel(self, event: dict[str, Any]) -> None:
        if event["channel"] in self.subscribed:
            await self.send_json(
                {"type": "channel", "channel": event["channel"], "data": event["data"]}
            )

    async def chat_read(self, event: dict[str, Any]) -> None:
        if event["channel"] in self.subscribed:
            await self.send_json(
                {
                    "type": "read",
                    "channel": event["channel"],
                    "last_read_seq": event["last_read_seq"],
                }
            )

    async def chat_typing(self, event: dict[str, Any]) -> None:
        if event["channel"] in self.subscribed and event["user"]["id"] != self.user_id:
            await self.send_json(
                {
                    "type": "typing",
                    "channel": event["channel"],
                    "thread": event["thread"],
                    "user": event["user"],
                }
            )

    async def chat_presence(self, event: dict[str, Any]) -> None:
        changes = [
            {"user": user, "online": online}
            for user, online in event["changes"]
            if user != self.user_id
        ]
        if changes:
            await self.send_json({"type": "presence_changes", "changes": changes})

    async def chat_notifications(self, event: dict[str, Any]) -> None:
        await self.send_json({"type": "notifications"})

    async def chat_signed_out(self, event: dict[str, Any]) -> None:
        """This device, or every device of the person, was signed out (apps/accounts/devices.py)."""
        devices = event["devices"]
        if devices is None or self.device_id in devices:
            await self.close(code=NOT_SIGNED_IN)

    async def chat_access(self, event: dict[str, Any]) -> None:
        readable = await self._readable()
        if readable is None:
            await self.close(code=NOT_A_MEMBER)
            return
        await self._subscribe(readable)
