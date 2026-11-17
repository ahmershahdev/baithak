from collections.abc import AsyncIterator
from typing import Any

import pytest
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.test import Client

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.consumers import NOT_A_MEMBER, NOT_SIGNED_IN
from apps.chat.models import Channel, ChannelMember
from apps.chat.services import create_default_channel
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.workspaces.models import Member, Workspace
from config.asgi import application
from config.routing import websocket_urlpatterns
from tests.accounts.factories import make_user

# Consumers reach the database from another thread, so data must really be committed.
pytestmark = pytest.mark.django_db(transaction=True)

PATH = "/ws/workspaces/team/"
router: Any = URLRouter(websocket_urlpatterns)  # type: ignore[arg-type]


@pytest.fixture
def owner() -> User:
    return make_user(username="owner")


@pytest.fixture
def workspace(owner: User) -> Workspace:
    workspace = Workspace.objects.create(name="Team", slug="team", created_by=owner)
    Member.objects.create(workspace=workspace, user=owner, role=Role.OWNER)
    create_default_channel(workspace, owner)
    return workspace


@pytest.fixture
def general(workspace: Workspace) -> Channel:
    return Channel.objects.for_workspace(workspace).get(name="general")


def join(workspace: Workspace, role: Role, username: str) -> User:
    user = make_user(username=username)
    Member.objects.create(workspace=workspace, user=user, role=role)
    return user


def as_user(user: User | AnonymousUser) -> Any:
    """The routed consumers with `user` in the scope, as AuthMiddlewareStack would put it."""

    async def app(scope: Any, receive: Any, send: Any) -> None:
        await router({**scope, "user": user}, receive, send)

    return app


async def connect(user: User | AnonymousUser) -> tuple[WebsocketCommunicator, bool, Any]:
    socket = WebsocketCommunicator(as_user(user), PATH)
    connected, code = await socket.connect()
    return socket, connected, code


@pytest.fixture
async def sockets() -> AsyncIterator[list[WebsocketCommunicator]]:
    opened: list[WebsocketCommunicator] = []
    yield opened
    for socket in opened:
        await socket.disconnect()


async def open_socket(user: User, opened: list[WebsocketCommunicator]) -> WebsocketCommunicator:
    socket, connected, _ = await connect(user)
    assert connected
    opened.append(socket)
    return socket


post = database_sync_to_async(messages.post)


class TestConnecting:
    async def test_signed_out_is_refused(self, workspace: Workspace) -> None:
        _, connected, code = await connect(AnonymousUser())

        assert (connected, code) == (False, NOT_SIGNED_IN)

    async def test_someone_outside_the_workspace_is_refused(self, workspace: Workspace) -> None:
        stranger = await database_sync_to_async(make_user)(username="stranger")

        _, connected, code = await connect(stranger)

        assert (connected, code) == (False, NOT_A_MEMBER)

    async def test_a_member_hears_the_channels_they_can_read(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        socket = await open_socket(owner, sockets)

        assert await socket.receive_json_from() == {
            "type": "subscribed",
            "channels": [general.pk],
        }

    async def test_ping_gets_pong(
        self, owner: User, workspace: Workspace, sockets: list[WebsocketCommunicator]
    ) -> None:
        socket = await open_socket(owner, sockets)
        await socket.receive_json_from()

        await socket.send_json_to({"type": "ping"})

        assert await socket.receive_json_from() == {"type": "pong"}

    async def test_anything_else_from_the_client_is_ignored(
        self, owner: User, workspace: Workspace, sockets: list[WebsocketCommunicator]
    ) -> None:
        socket = await open_socket(owner, sockets)
        await socket.receive_json_from()

        await socket.send_json_to({"type": "message", "body": "sneaky"})

        assert await socket.receive_nothing()


class TestThroughTheRealApp:
    """The full ASGI stack: session cookie, origin check and routing, as a browser connects."""

    def _headers(
        self, user: User, origin: bytes = b"http://localhost"
    ) -> list[tuple[bytes, bytes]]:
        client = Client()
        client.force_login(user)
        cookie = client.cookies["sessionid"].value
        return [(b"cookie", f"sessionid={cookie}".encode()), (b"origin", origin)]

    async def test_a_signed_in_member_connects_with_the_session_cookie(
        self, owner: User, workspace: Workspace
    ) -> None:
        headers = await database_sync_to_async(self._headers)(owner)
        socket = WebsocketCommunicator(application, PATH, headers=headers)

        connected, _ = await socket.connect()

        assert connected
        assert (await socket.receive_json_from())["type"] == "subscribed"
        await socket.disconnect()

    async def test_a_foreign_origin_is_refused(self, owner: User, workspace: Workspace) -> None:
        headers = await database_sync_to_async(self._headers)(owner, b"https://evil.example")
        socket = WebsocketCommunicator(application, PATH, headers=headers)

        connected, _ = await socket.connect()

        assert not connected


class TestBroadcast:
    async def test_a_saved_message_reaches_every_open_tab_in_the_channel(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        tabs = [await open_socket(owner, sockets), await open_socket(bilal, sockets)]
        for tab in tabs:
            await tab.receive_json_from()

        message, _ = await post(general, owner, "Salaam")

        for tab in tabs:
            event = await tab.receive_json_from()
            assert (event["type"], event["channel"], event["event"]) == ("message", general.pk, 1)
            assert event["message"]["body"] == "Salaam"
            assert event["message"]["seq"] == message.seq

    async def test_edits_and_deletes_arrive_with_their_new_event(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        socket = await open_socket(owner, sockets)
        await socket.receive_json_from()
        message, _ = await post(general, owner, "Teh plan")
        await socket.receive_json_from()

        await database_sync_to_async(messages.edit)(message, "The plan")
        edited = await socket.receive_json_from()
        await database_sync_to_async(messages.delete)(message)
        deleted = await socket.receive_json_from()

        assert (edited["event"], edited["message"]["body"]) == (2, "The plan")
        assert (deleted["event"], deleted["message"]["deleted"]) == (3, True)

    async def test_a_private_channel_is_silent_to_people_outside_it(
        self,
        owner: User,
        workspace: Workspace,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        secret = await database_sync_to_async(self._private)(workspace, owner)
        admin = await database_sync_to_async(join)(workspace, Role.ADMIN, "admin")
        socket = await open_socket(admin, sockets)
        await socket.receive_json_from()

        await post(secret, owner, "Only for us")

        assert await socket.receive_nothing()

    async def test_being_added_subscribes_an_open_socket(
        self,
        owner: User,
        workspace: Workspace,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        from rest_framework.test import APIClient

        secret = await database_sync_to_async(self._private)(workspace, owner)
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        socket = await open_socket(bilal, sockets)
        before = await socket.receive_json_from()

        def add() -> int:
            api = APIClient()
            api.force_authenticate(owner)
            response = api.post(
                f"/api/v1/workspaces/team/channels/{secret.pk}/members/",
                {"user_id": bilal.pk},
                format="json",
            )
            return int(response.status_code)

        assert await database_sync_to_async(add)() == 201
        after = await socket.receive_json_from()
        await post(secret, owner, "Welcome in")
        heard = await socket.receive_json_from()

        assert secret.pk not in before["channels"]
        assert secret.pk in after["channels"]
        assert heard["message"]["body"] == "Welcome in"

    async def test_leaving_unsubscribes(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        from rest_framework.test import APIClient

        secret = await database_sync_to_async(self._private)(workspace, owner)
        socket = await open_socket(owner, sockets)
        await socket.receive_json_from()

        def leave() -> None:
            api = APIClient()
            api.force_authenticate(owner)
            api.post(f"/api/v1/workspaces/team/channels/{secret.pk}/leave/")

        await database_sync_to_async(leave)()
        after = await socket.receive_json_from()
        await post(secret, owner, "Nobody hears this")

        assert after["channels"] == [general.pk]
        assert await socket.receive_nothing()

    async def test_removal_from_the_workspace_closes_the_socket(
        self,
        owner: User,
        workspace: Workspace,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        from rest_framework.test import APIClient

        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        socket = await open_socket(bilal, sockets)
        await socket.receive_json_from()

        def remove() -> None:
            api = APIClient()
            api.force_authenticate(owner)
            api.delete(f"/api/v1/workspaces/team/members/{bilal.pk}/")

        await database_sync_to_async(remove)()

        closed = await socket.receive_output()
        assert closed == {"type": "websocket.close", "code": NOT_A_MEMBER}
        sockets.remove(socket)

    async def test_channel_changes_are_broadcast(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        from rest_framework.test import APIClient

        socket = await open_socket(owner, sockets)
        await socket.receive_json_from()

        def set_topic() -> None:
            api = APIClient()
            api.force_authenticate(owner)
            api.patch(
                f"/api/v1/workspaces/team/channels/{general.pk}/",
                {"topic": "Say hello"},
                format="json",
            )

        await database_sync_to_async(set_topic)()
        event = await socket.receive_json_from()

        assert (event["type"], event["data"]["topic"]) == ("channel", "Say hello")
        assert "is_member" not in event["data"]

    @staticmethod
    def _private(workspace: Workspace, owner: User) -> Channel:
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE, created_by=owner
        )
        ChannelMember.objects.create(channel=secret, user=owner)
        return secret
