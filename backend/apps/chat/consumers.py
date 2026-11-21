from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.chat.access import readable_channels
from apps.chat.events import channel_group, user_group
from apps.workspaces.models import Member

# Close codes in the 4000 range are free for applications (RFC 6455, 7.4.2).
NOT_SIGNED_IN = 4401
NOT_A_MEMBER = 4404


class WorkspaceConsumer(AsyncJsonWebsocketConsumer):
    """One socket per open workspace tab. It hears every channel the person may read.

    Which channels that is comes from readable_channels, the same rule as the REST API, worked
    out on connect and again whenever the person's access changes.
    """

    user_id: int
    slug: str
    subscribed: set[int]

    async def connect(self) -> None:
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=NOT_SIGNED_IN)
            return
        self.user_id = user.pk
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.subscribed = set()
        channels = await self._readable()
        if channels is None:
            await self.close(code=NOT_A_MEMBER)
            return
        await self.accept()
        await self.channel_layer.group_add(user_group(self.user_id), self.channel_name)
        await self._subscribe(channels)

    async def disconnect(self, code: int) -> None:
        if not hasattr(self, "subscribed"):
            return
        for channel_id in self.subscribed:
            await self.channel_layer.group_discard(channel_group(channel_id), self.channel_name)
        await self.channel_layer.group_discard(user_group(self.user_id), self.channel_name)

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        # The client sends little: a ping to keep proxies from closing an idle socket.
        # Messages go through the REST API, so they are saved before anyone hears them.
        if isinstance(content, dict) and content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    @database_sync_to_async
    def _readable(self) -> set[int] | None:
        member = (
            Member.objects.select_related("workspace")
            .filter(workspace__slug=self.slug, user_id=self.user_id)
            .first()
        )
        if member is None:
            return None
        return set(readable_channels(member).values_list("pk", flat=True))

    async def _subscribe(self, channels: set[int]) -> None:
        for channel_id in channels - self.subscribed:
            await self.channel_layer.group_add(channel_group(channel_id), self.channel_name)
        for channel_id in self.subscribed - channels:
            await self.channel_layer.group_discard(channel_group(channel_id), self.channel_name)
        self.subscribed = channels
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

    async def chat_access(self, event: dict[str, Any]) -> None:
        channels = await self._readable()
        if channels is None:
            await self.close(code=NOT_A_MEMBER)
            return
        await self._subscribe(channels)
