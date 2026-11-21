import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember, Message
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.workspaces.models import AuditEvent, Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db


def join(workspace: Workspace, role: Role, username: str) -> User:
    user = make_user(username=username)
    Member.objects.create(workspace=workspace, user=user, role=role)
    return user


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


def url(channel: Channel, suffix: str = "") -> str:
    return f"/api/v1/workspaces/karachi-team/channels/{channel.pk}/messages/{suffix}"


def send(api: APIClient, channel: Channel, body: str, client_id: str = "") -> dict[str, object]:
    payload = {"body": body} | ({"client_id": client_id} if client_id else {})
    response = api.post(url(channel), payload, format="json")
    assert response.status_code in (200, 201), response.json()
    return dict(response.json())


class TestSending:
    def test_messages_take_increasing_seq_and_event(self, api: APIClient, general: Channel) -> None:
        first = send(api, general, "Salaam")
        second = send(api, general, "  Chai at four?  ")

        assert (first["seq"], first["event"]) == (1, 1)
        assert (second["seq"], second["event"]) == (2, 2)
        assert second["body"] == "Chai at four?"
        general.refresh_from_db()
        assert (general.last_seq, general.last_event) == (2, 2)

    def test_a_retried_send_is_stored_once(self, api: APIClient, general: Channel) -> None:
        first = api.post(url(general), {"body": "Hi", "client_id": "abc-1"}, format="json")
        retry = api.post(url(general), {"body": "Hi", "client_id": "abc-1"}, format="json")

        assert first.status_code == 201
        assert retry.status_code == 200
        assert retry.json()["seq"] == first.json()["seq"]
        assert Message.objects.filter(channel=general).count() == 1

    def test_the_same_client_id_from_someone_else_is_a_new_message(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        send(api, general, "Hi", "same-id")
        bilal = join(workspace, Role.MEMBER, "bilal")
        ChannelMember.objects.create(channel=general, user=bilal)
        api.force_authenticate(bilal)

        send(api, general, "Hi too", "same-id")

        assert Message.objects.filter(channel=general).count() == 2

    @pytest.mark.parametrize("body", ["", "   ", "x" * 4001])
    def test_empty_or_long_bodies_are_rejected(
        self, api: APIClient, general: Channel, body: str
    ) -> None:
        response = api.post(url(general), {"body": body}, format="json")

        assert response.status_code == 400

    def test_bad_client_ids_are_rejected(self, api: APIClient, general: Channel) -> None:
        response = api.post(url(general), {"body": "Hi", "client_id": "no spaces"}, format="json")

        assert response.status_code == 400

    def test_you_must_be_in_the_channel_to_post(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        api.force_authenticate(join(workspace, Role.MEMBER, "bilal"))

        response = api.post(url(general), {"body": "Hi"}, format="json")

        assert response.status_code == 403
        assert response.json() == {"detail": "Join the channel to post in it."}

    def test_nobody_posts_in_an_archived_channel(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        old = Channel.objects.create(workspace=workspace, name="old", kind=ChannelKind.PUBLIC)
        ChannelMember.objects.create(channel=old, user=owner)
        api.patch(
            f"/api/v1/workspaces/karachi-team/channels/{old.pk}/", {"archived": True}, format="json"
        )

        response = api.post(url(old), {"body": "Hello?"}, format="json")

        assert response.status_code == 403
        assert response.json() == {"detail": "This channel is archived."}


@pytest.mark.django_db(transaction=True)
def test_concurrent_sends_get_distinct_gap_free_seqs(owner: User) -> None:
    """Saved first under a row lock: parallel senders never share or skip a number."""
    workspace = Workspace.objects.create(name="Race", slug="race")
    channel = Channel.objects.create(workspace=workspace, name="race", kind=ChannelKind.PUBLIC)
    errors: list[Exception] = []

    def worker(n: int) -> None:
        try:
            for i in range(5):
                messages.post(channel, owner, f"{n}-{i}")
        # Any failure in a thread would otherwise vanish; collect it for the assert below.
        except Exception as error:
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    seqs = sorted(
        s for s in Message.objects.filter(channel=channel).values_list("seq", flat=True) if s
    )
    assert seqs == list(range(1, 21))
    channel.refresh_from_db()
    assert (channel.last_seq, channel.last_event) == (20, 20)


class TestEditingAndDeleting:
    def test_the_author_edits_and_it_takes_a_new_event(
        self, api: APIClient, general: Channel
    ) -> None:
        send(api, general, "Teh plan")
        send(api, general, "Second")

        edited = api.patch(url(general, "1/"), {"body": "The plan"}, format="json").json()

        assert (edited["seq"], edited["event"], edited["body"]) == (1, 3, "The plan")
        assert edited["edited_at"] is not None

    def test_an_unchanged_edit_changes_nothing(self, api: APIClient, general: Channel) -> None:
        send(api, general, "Same")

        edited = api.patch(url(general, "1/"), {"body": "Same"}, format="json").json()

        assert (edited["event"], edited["edited_at"]) == (1, None)

    def test_others_cannot_edit(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        send(api, general, "Mine")
        api.force_authenticate(join(workspace, Role.ADMIN, "admin"))

        response = api.patch(url(general, "1/"), {"body": "Yours now"}, format="json")

        assert response.status_code == 403

    def test_deleting_keeps_the_row_and_drops_the_text(
        self, api: APIClient, general: Channel
    ) -> None:
        send(api, general, "Oops")

        response = api.delete(url(general, "1/"))

        assert response.status_code == 204
        message = Message.objects.get(channel=general, seq=1)
        assert (message.body, message.deleted, message.event) == ("", True, 2)

    def test_a_deleted_message_cannot_be_edited_or_deleted_again(
        self, api: APIClient, general: Channel
    ) -> None:
        send(api, general, "Oops")
        api.delete(url(general, "1/"))

        edited = api.patch(url(general, "1/"), {"body": "Back"}, format="json")
        deleted = api.delete(url(general, "1/"))

        assert (edited.status_code, deleted.status_code) == (403, 403)

    def test_an_admin_deleting_someone_elses_message_is_audited(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        bilal = join(workspace, Role.MEMBER, "bilal")
        ChannelMember.objects.create(channel=general, user=bilal)
        api.force_authenticate(bilal)
        send(api, general, "Something rude")
        admin = join(workspace, Role.ADMIN, "admin")
        api.force_authenticate(admin)

        response = api.delete(url(general, "1/"))

        assert response.status_code == 204
        event = AuditEvent.objects.for_workspace(workspace).order_by("-id").first()
        assert event is not None
        assert (event.action, event.changes) == ("message.delete", {"channel": "general", "seq": 1})

    def test_authors_deleting_their_own_are_not_audited(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        send(api, general, "Mine")
        before = AuditEvent.objects.for_workspace(workspace).count()

        api.delete(url(general, "1/"))

        assert AuditEvent.objects.for_workspace(workspace).count() == before

    def test_members_cannot_delete_others(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        send(api, general, "Owner's words")
        api.force_authenticate(join(workspace, Role.MEMBER, "bilal"))

        response = api.delete(url(general, "1/"))

        assert response.status_code == 403

    def test_unknown_messages_are_404(self, api: APIClient, general: Channel) -> None:
        response = api.patch(url(general, "99/"), {"body": "x"}, format="json")

        assert response.status_code == 404


class TestHistory:
    def test_the_newest_page_comes_oldest_first_with_has_more(
        self, api: APIClient, general: Channel, owner: User
    ) -> None:
        for n in range(1, 56):
            messages.post(general, owner, f"m{n}")

        page = api.get(url(general)).json()
        older = api.get(url(general), {"before": page["messages"][0]["seq"]}).json()

        assert [m["seq"] for m in page["messages"]] == list(range(6, 56))
        assert page["has_more"] is True
        assert (page["last_seq"], page["last_event"]) == (55, 55)
        assert [m["seq"] for m in older["messages"]] == list(range(1, 6))
        assert older["has_more"] is False

    def test_catch_up_returns_new_edited_and_deleted_messages_after_an_event(
        self, api: APIClient, general: Channel, owner: User
    ) -> None:
        for n in range(1, 4):
            messages.post(general, owner, f"m{n}")
        seen_event = 3
        messages.edit(Message.objects.get(channel=general, seq=1), "m1 edited")
        messages.post(general, owner, "m4")
        messages.delete(Message.objects.get(channel=general, seq=2))

        caught = api.get(url(general), {"after_event": seen_event}).json()

        assert [(m["seq"], m["event"]) for m in caught["messages"]] == [(1, 4), (4, 5), (2, 6)]
        assert caught["messages"][2]["deleted"] is True
        assert caught["messages"][2]["body"] == ""
        assert caught["last_event"] == 6
        assert caught["has_more"] is False

    def test_catch_up_is_capped_and_says_there_is_more(
        self, api: APIClient, general: Channel, owner: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from apps.chat import message_views

        monkeypatch.setattr(message_views, "CATCH_UP_LIMIT", 3)
        for n in range(5):
            messages.post(general, owner, f"m{n}")

        caught = api.get(url(general), {"after_event": 0}).json()

        assert [m["event"] for m in caught["messages"]] == [1, 2, 3]
        assert caught["has_more"] is True

    @pytest.mark.parametrize(("name", "value"), [("before", "abc"), ("after_event", "-1")])
    def test_bad_numbers_are_400(
        self, api: APIClient, general: Channel, name: str, value: str
    ) -> None:
        assert api.get(url(general), {name: value}).status_code == 400

    def test_reading_history_needs_no_membership_in_a_public_channel(
        self, api: APIClient, workspace: Workspace, general: Channel, owner: User
    ) -> None:
        messages.post(general, owner, "Visible to every member")
        api.force_authenticate(join(workspace, Role.MEMBER, "bilal"))

        assert len(api.get(url(general)).json()["messages"]) == 1
