from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
import redis
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import Client

from apps.accounts import devices
from apps.accounts.models import User
from apps.chat import messages, presence
from apps.chat.consumers import NOT_A_MEMBER, NOT_SIGNED_IN
from apps.chat.models import Channel, ChannelMember
from apps.chat.reads import mark_read
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


@pytest.fixture(autouse=True)
def _clear_presence() -> Iterator[None]:
    """Presence lives in real Redis (under the test prefix); start each test from nobody."""
    yield
    client = redis.from_url(settings.REDIS_URL)
    keys = list(client.scan_iter(f"{settings.PRESENCE_KEY_PREFIX}:*"))
    if keys:
        client.delete(*keys)
    client.close()


@pytest.fixture(autouse=True)
def _quick_presence_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.chat.consumers.PRESENCE_BATCH_SECONDS", 0.05)


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

# Every socket also hears who is online; tests about other things look past it.
PRESENCE = {"presence", "presence_changes"}


async def receive(socket: WebsocketCommunicator) -> Any:
    while True:
        event = await socket.receive_json_from()
        if event["type"] not in PRESENCE:
            return event


async def quiet(socket: WebsocketCommunicator) -> bool:
    while not await socket.receive_nothing():
        if (await socket.receive_json_from())["type"] not in PRESENCE:
            return False
    return True


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

        assert await receive(socket) == {
            "type": "subscribed",
            "channels": [general.pk],
        }

    async def test_ping_gets_pong(
        self, owner: User, workspace: Workspace, sockets: list[WebsocketCommunicator]
    ) -> None:
        socket = await open_socket(owner, sockets)
        await receive(socket)

        await socket.send_json_to({"type": "ping"})

        assert await receive(socket) == {"type": "pong"}

    async def test_anything_else_from_the_client_is_ignored(
        self, owner: User, workspace: Workspace, sockets: list[WebsocketCommunicator]
    ) -> None:
        socket = await open_socket(owner, sockets)
        await receive(socket)

        await socket.send_json_to({"type": "message", "body": "sneaky"})

        assert await quiet(socket)


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
        assert (await receive(socket))["type"] == "subscribed"
        await socket.disconnect()

    async def test_signing_a_device_out_closes_only_its_sockets(
        self, owner: User, workspace: Workspace
    ) -> None:
        def session(user: User) -> tuple[list[tuple[bytes, bytes]], int]:
            client = Client()
            client.force_login(user)
            cookie = client.cookies["sessionid"].value
            headers = [
                (b"cookie", f"sessionid={cookie}".encode()),
                (b"origin", b"http://localhost"),
            ]
            return headers, client.session[devices.SESSION_KEY]

        laptop_headers, laptop = await database_sync_to_async(session)(owner)
        phone_headers, _ = await database_sync_to_async(session)(owner)
        laptop_socket = WebsocketCommunicator(application, PATH, headers=laptop_headers)
        phone_socket = WebsocketCommunicator(application, PATH, headers=phone_headers)
        assert (await laptop_socket.connect())[0]
        assert (await phone_socket.connect())[0]
        await receive(laptop_socket)
        await receive(phone_socket)

        await database_sync_to_async(devices.end)(owner, laptop)

        output = await laptop_socket.receive_output()
        while output["type"] == "websocket.send":
            output = await laptop_socket.receive_output()
        assert output == {"type": "websocket.close", "code": NOT_SIGNED_IN}
        assert await quiet(phone_socket)
        again = WebsocketCommunicator(application, PATH, headers=laptop_headers)
        assert await again.connect() == (False, NOT_SIGNED_IN)
        await phone_socket.disconnect()

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
            await receive(tab)

        message, _ = await post(general, owner, "Salaam")

        for tab in tabs:
            event = await receive(tab)
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
        await receive(socket)
        message, _ = await post(general, owner, "Teh plan")
        await receive(socket)
        assert (await receive(socket))["type"] == "read"

        await database_sync_to_async(messages.edit)(message, "The plan")
        edited = await receive(socket)
        await database_sync_to_async(messages.delete)(message)
        deleted = await receive(socket)

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
        await receive(socket)

        await post(secret, owner, "Only for us")

        assert await quiet(socket)

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
        before = await receive(socket)

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
        after = await receive(socket)
        await post(secret, owner, "Welcome in")
        heard = await receive(socket)

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
        await receive(socket)

        def leave() -> None:
            api = APIClient()
            api.force_authenticate(owner)
            api.post(f"/api/v1/workspaces/team/channels/{secret.pk}/leave/")

        await database_sync_to_async(leave)()
        after = await receive(socket)
        await post(secret, owner, "Nobody hears this")

        assert after["channels"] == [general.pk]
        assert await quiet(socket)

    async def test_removal_from_the_workspace_closes_the_socket(
        self,
        owner: User,
        workspace: Workspace,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        from rest_framework.test import APIClient

        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        socket = await open_socket(bilal, sockets)
        await receive(socket)

        def remove() -> None:
            api = APIClient()
            api.force_authenticate(owner)
            api.delete(f"/api/v1/workspaces/team/members/{bilal.pk}/")

        await database_sync_to_async(remove)()

        closed = await socket.receive_output()
        while closed["type"] == "websocket.send":
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
        await receive(socket)

        def set_topic() -> None:
            api = APIClient()
            api.force_authenticate(owner)
            api.patch(
                f"/api/v1/workspaces/team/channels/{general.pk}/",
                {"topic": "Say hello"},
                format="json",
            )

        await database_sync_to_async(set_topic)()
        event = await receive(socket)

        assert (event["type"], event["data"]["topic"]) == ("channel", "Say hello")
        assert "is_member" not in event["data"]

    @staticmethod
    def _private(workspace: Workspace, owner: User) -> Channel:
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE, created_by=owner
        )
        ChannelMember.objects.create(channel=secret, user=owner)
        return secret


class TestReadMarkers:
    async def test_a_marker_reaches_every_device_of_that_person_only(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        phone, laptop = await open_socket(owner, sockets), await open_socket(owner, sockets)
        other = await open_socket(bilal, sockets)
        for socket in (phone, laptop, other):
            await receive(socket)
        await post(general, bilal, "Salaam")
        for socket in (phone, laptop, other):
            assert (await receive(socket))["type"] == "message"

        await database_sync_to_async(mark_read)(general, owner.pk, 1)

        for socket in (phone, laptop):
            assert await receive(socket) == {
                "type": "read",
                "channel": general.pk,
                "last_read_seq": 1,
            }
        assert await quiet(other)


class TestThreads:
    async def test_a_reply_arrives_then_its_parent_with_the_new_count(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        socket = await open_socket(bilal, sockets)
        await receive(socket)
        first, _ = await post(general, owner, "Lunch?")
        await receive(socket)

        await database_sync_to_async(messages.post)(general, owner, "Biryani", parent=first)

        reply = await receive(socket)
        parent = await receive(socket)
        assert (reply["event"], reply["message"]["parent_seq"], reply["message"]["seq"]) == (
            2,
            1,
            None,
        )
        assert (parent["event"], parent["message"]["reply_count"]) == (3, 1)


async def raw(socket: WebsocketCommunicator, kind: str, wait: float = 1) -> Any:
    """The next event of `kind`, skipping anything else."""
    while True:
        event = await socket.receive_json_from(timeout=wait)
        if event["type"] == kind:
            return event


class TestPresence:
    async def test_a_new_socket_hears_who_is_online(
        self, owner: User, workspace: Workspace, sockets: list[WebsocketCommunicator]
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        await open_socket(owner, sockets)

        socket = await open_socket(bilal, sockets)

        snapshot = await raw(socket, "presence")
        assert snapshot["online"] == sorted([owner.pk, bilal.pk])

    async def test_others_hear_someone_come_and_go(
        self, owner: User, workspace: Workspace, sockets: list[WebsocketCommunicator]
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        watcher = await open_socket(owner, sockets)
        await raw(watcher, "presence")

        tab = await open_socket(bilal, sockets)
        came = await raw(watcher, "presence_changes")
        await tab.disconnect()
        sockets.remove(tab)
        went = await raw(watcher, "presence_changes")

        assert came["changes"] == [{"user": bilal.pk, "online": True}]
        assert went["changes"] == [{"user": bilal.pk, "online": False}]

    async def test_a_crowd_arriving_together_is_announced_together(
        self,
        owner: User,
        workspace: Workspace,
        sockets: list[WebsocketCommunicator],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("apps.chat.consumers.PRESENCE_BATCH_SECONDS", 2.0)
        watcher = await open_socket(owner, sockets)
        await raw(watcher, "presence")
        crowd = [
            await database_sync_to_async(join)(workspace, Role.MEMBER, f"person{number}")
            for number in range(5)
        ]

        for person in crowd:
            await open_socket(person, sockets)
        batch = await raw(watcher, "presence_changes", wait=5)

        assert sorted(change["user"] for change in batch["changes"]) == sorted(
            person.pk for person in crowd
        )

    async def test_closing_one_of_two_tabs_keeps_the_person_online(
        self, owner: User, workspace: Workspace, sockets: list[WebsocketCommunicator]
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        watcher = await open_socket(owner, sockets)
        await raw(watcher, "presence")
        first = await open_socket(bilal, sockets)
        await open_socket(bilal, sockets)
        await raw(watcher, "presence_changes")

        await first.disconnect()
        sockets.remove(first)

        assert await watcher.receive_nothing(timeout=0.3)
        assert bilal.pk in await presence.online_users(workspace.pk)

    async def test_people_in_another_workspace_hear_nothing(
        self, owner: User, workspace: Workspace, sockets: list[WebsocketCommunicator]
    ) -> None:
        watcher = await open_socket(owner, sockets)
        await raw(watcher, "presence")
        other = await database_sync_to_async(Workspace.objects.create)(
            name="Other", slug="other", created_by=owner
        )
        stranger = await database_sync_to_async(make_user)(username="stranger")
        await database_sync_to_async(Member.objects.create)(
            workspace=other, user=stranger, role=Role.OWNER
        )
        socket = WebsocketCommunicator(as_user(stranger), "/ws/workspaces/other/")
        connected, _ = await socket.connect()
        assert connected
        sockets.append(socket)

        assert await watcher.receive_nothing()


class TestTyping:
    async def test_typing_reaches_the_others_in_the_channel_not_me(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        me = await open_socket(owner, sockets)
        other = await open_socket(bilal, sockets)
        await receive(me)
        await receive(other)

        await me.send_json_to({"type": "typing", "channel": general.pk, "thread": None})

        event = await receive(other)
        assert (event["type"], event["channel"], event["thread"]) == ("typing", general.pk, None)
        assert event["user"]["username"] == "owner"
        assert await quiet(me)

    async def test_notices_are_held_to_one_every_few_seconds(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        me = await open_socket(owner, sockets)
        other = await open_socket(bilal, sockets)
        await receive(me)
        await receive(other)

        for _ in range(3):
            await me.send_json_to({"type": "typing", "channel": general.pk})
        await me.send_json_to({"type": "typing", "channel": general.pk, "thread": 1})

        first, in_thread = await receive(other), await receive(other)
        assert (first["thread"], in_thread["thread"]) == (None, 1)
        assert await quiet(other)

    @pytest.mark.parametrize("channel", ["general", 999_999, None])
    async def test_nothing_for_a_channel_i_am_not_in_or_garbage(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
        channel: object,
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        me = await open_socket(bilal, sockets)
        other = await open_socket(owner, sockets)
        await receive(me)
        await receive(other)

        # bilal reads #general (public) but has not joined it, so can't be typing there.
        target = general.pk if channel == "general" else channel
        await me.send_json_to({"type": "typing", "channel": target})

        assert await quiet(other)


class TestNotifications:
    async def test_a_mention_reaches_the_person_named_only(
        self,
        owner: User,
        workspace: Workspace,
        general: Channel,
        sockets: list[WebsocketCommunicator],
    ) -> None:
        bilal = await database_sync_to_async(join)(workspace, Role.MEMBER, "bilal")
        theirs = await open_socket(bilal, sockets)
        mine = await open_socket(owner, sockets)
        await receive(theirs)
        await receive(mine)

        await post(general, owner, "@bilal look at this")

        assert (await receive(theirs))["type"] == "message"
        assert await receive(theirs) == {"type": "notifications"}
        assert (await receive(mine))["type"] == "message"
        assert (await receive(mine))["type"] == "read"
        assert await quiet(mine)
