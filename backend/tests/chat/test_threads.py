import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember, Message
from apps.core.roles import Role
from apps.workspaces.models import AuditEvent, Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/workspaces/karachi-team/channels/"


@pytest.fixture
def owner() -> User:
    return make_user(username="owner")


@pytest.fixture
def workspace(api: APIClient, owner: User) -> Workspace:
    api.force_authenticate(owner)
    response = api.post("/api/v1/workspaces/", {"name": "Karachi Team"}, format="json")
    return Workspace.objects.get(slug=response.json()["slug"])


@pytest.fixture
def general(workspace: Workspace) -> Channel:
    return Channel.objects.for_workspace(workspace).get(name="general")


@pytest.fixture
def bilal(workspace: Workspace, general: Channel) -> User:
    user = make_user(username="bilal")
    Member.objects.create(workspace=workspace, user=user, role=Role.MEMBER)
    ChannelMember.objects.create(channel=general, user=user)
    return user


@pytest.fixture
def first(general: Channel, bilal: User) -> Message:
    message, _ = messages.post(general, bilal, "Who is bringing samosas?")
    return message


def thread_url(channel: Channel, seq: int, suffix: str = "") -> str:
    return f"{BASE}{channel.pk}/messages/{seq}/replies/{suffix}"


def reply(
    api: APIClient, channel: Channel, seq: int, body: str, **extra: object
) -> dict[str, object]:
    response = api.post(thread_url(channel, seq), {"body": body} | extra, format="json")
    assert response.status_code in (200, 201), response.json()
    return dict(response.json())


class TestReplying:
    def test_a_reply_stays_out_of_the_channel(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        sent = reply(api, general, 1, "I will")

        assert (sent["seq"], sent["parent_seq"], sent["thread_seq"]) == (None, 1, 1)
        history = api.get(f"{BASE}{general.pk}/messages/").json()
        assert [m["body"] for m in history["messages"]] == ["Who is bringing samosas?"]
        assert history["last_seq"] == 1

    def test_the_parent_counts_replies_with_a_new_event(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        reply(api, general, 1, "I will")
        second = reply(api, general, 1, "With chutney")

        first.refresh_from_db()
        assert (first.reply_count, first.event) == (2, 5)
        assert second["event"] == 4
        assert first.last_reply_at is not None

    def test_catching_up_brings_the_reply_and_the_new_count(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        reply(api, general, 1, "I will")

        page = api.get(f"{BASE}{general.pk}/messages/", {"after_event": 1}).json()

        assert [(m["event"], m["body"], m["reply_count"]) for m in page["messages"]] == [
            (2, "I will", 0),
            (3, "Who is bringing samosas?", 1),
        ]

    def test_also_sending_to_the_channel_gives_it_a_place_there(
        self, api: APIClient, owner: User, general: Channel, first: Message, bilal: User
    ) -> None:
        api.force_authenticate(bilal)
        sent = reply(api, general, 1, "Everyone: samosas at four", also_in_channel=True)

        assert (sent["seq"], sent["also_in_channel"], sent["parent_seq"]) == (2, True, 1)
        api.force_authenticate(owner)
        channel = next(c for c in api.get(BASE).json() if c["id"] == general.pk)
        assert channel["unread"] == 2

    def test_a_reply_kept_in_the_thread_is_not_unread_in_the_channel(
        self, api: APIClient, owner: User, general: Channel, first: Message, bilal: User
    ) -> None:
        api.force_authenticate(bilal)
        reply(api, general, 1, "Just between us")

        api.force_authenticate(owner)
        channel = next(c for c in api.get(BASE).json() if c["id"] == general.pk)
        assert channel["unread"] == 1

    def test_a_retried_reply_is_stored_once(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        reply(api, general, 1, "I will", client_id="abc")
        again = api.post(
            thread_url(general, 1), {"body": "I will", "client_id": "abc"}, format="json"
        )

        assert again.status_code == 200
        assert Message.objects.filter(parent=first).count() == 1

    def test_replies_do_not_nest(self, api: APIClient, general: Channel, first: Message) -> None:
        reply(api, general, 1, "Also here", also_in_channel=True)

        response = api.post(thread_url(general, 2), {"body": "Nested"}, format="json")

        assert response.status_code == 404

    def test_someone_outside_the_channel_cannot_reply(
        self, api: APIClient, workspace: Workspace, general: Channel, first: Message
    ) -> None:
        reader = make_user(username="reader")
        Member.objects.create(workspace=workspace, user=reader, role=Role.MEMBER)
        api.force_authenticate(reader)

        response = api.post(thread_url(general, 1), {"body": "Hi"}, format="json")

        assert response.status_code == 403

    def test_an_archived_channel_takes_no_replies(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        Channel.objects.filter(pk=general.pk).update(archived_at=timezone.now())

        response = api.post(thread_url(general, 1), {"body": "Late"}, format="json")

        assert response.status_code == 403


class TestReading:
    def test_a_thread_lists_its_parent_and_replies_oldest_first(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        for text in ("One", "Two", "Three"):
            reply(api, general, 1, text)

        body = api.get(thread_url(general, 1)).json()

        assert body["parent"]["body"] == "Who is bringing samosas?"
        assert [r["body"] for r in body["replies"]] == ["One", "Two", "Three"]
        assert body["has_more"] is False

    def test_after_skips_replies_already_seen(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        for text in ("One", "Two", "Three"):
            reply(api, general, 1, text)

        body = api.get(thread_url(general, 1), {"after": 2}).json()

        assert [r["thread_seq"] for r in body["replies"]] == [3]

    def test_a_missing_thread_is_404(self, api: APIClient, general: Channel) -> None:
        assert api.get(thread_url(general, 99)).status_code == 404


class TestEditingAndDeleting:
    def test_the_author_edits_a_reply(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        reply(api, general, 1, "I wil")

        response = api.patch(thread_url(general, 1, "1/"), {"body": "I will"}, format="json")

        assert (response.status_code, response.json()["body"]) == (200, "I will")
        assert response.json()["edited_at"] is not None

    def test_someone_else_cannot_edit_it(
        self, api: APIClient, general: Channel, first: Message, bilal: User
    ) -> None:
        reply(api, general, 1, "Mine")
        api.force_authenticate(bilal)

        response = api.patch(thread_url(general, 1, "1/"), {"body": "Yours"}, format="json")

        assert response.status_code == 403

    def test_an_admin_deleting_a_reply_is_audited_with_its_place(
        self,
        api: APIClient,
        owner: User,
        workspace: Workspace,
        general: Channel,
        first: Message,
        bilal: User,
    ) -> None:
        api.force_authenticate(bilal)
        reply(api, general, 1, "Oops")
        api.force_authenticate(owner)

        response = api.delete(thread_url(general, 1, "1/"))

        assert response.status_code == 204
        event = AuditEvent.objects.for_workspace(workspace).order_by("-id").first()
        assert event is not None
        assert (event.action, event.changes) == (
            "message.delete",
            {"channel": "general", "thread": 1, "reply": 1},
        )
        deleted = Message.objects.get(parent=first)
        assert (deleted.body, deleted.deleted) == ("", True)

    def test_a_missing_reply_is_404(self, api: APIClient, general: Channel, first: Message) -> None:
        response = api.patch(thread_url(general, 1, "7/"), {"body": "x"}, format="json")

        assert response.status_code == 404
