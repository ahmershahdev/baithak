import time
from dataclasses import dataclass
from typing import Any, cast

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.accounts.models import User
from apps.chat import presence
from apps.chat.access import readable_channels
from apps.chat.events import channel_group, user_group, workspace_group
from apps.core.presence import typing_due
from apps.workspaces.models import Member

# Close codes in the 4000 range are free for applications (RFC 6455, 7.4.2).
NOT_SIGNED_IN = 4401
NOT_A_MEMBER = 4404


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
        await self.channel_layer.group_send(
            workspace_group(self.workspace_id),
            {"type": "chat.presence", "user": self.user_id, "online": online},
        )

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
        if event["user"] != self.user_id:
            await self.send_json(
                {"type": "presence_change", "user": event["user"], "online": event["online"]}
            )

    async def chat_notifications(self, event: dict[str, Any]) -> None:
        await self.send_json({"type": "notifications"})

    async def chat_access(self, event: dict[str, Any]) -> None:
        readable = await self._readable()
        if readable is None:
            await self.close(code=NOT_A_MEMBER)
            return
        await self._subscribe(readable)
