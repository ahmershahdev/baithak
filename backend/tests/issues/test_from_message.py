from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember, Message
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.issues.models import Project
from apps.workspaces.models import AuditEvent, Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

ISSUES = "/api/v1/workspaces/karachi-team/projects/BAI/issues/"
CHANNELS = "/api/v1/workspaces/karachi-team/channels/"


@pytest.fixture
def owner() -> User:
    return make_user(username="owner")


@pytest.fixture
def workspace(api: APIClient, owner: User) -> Workspace:
    api.force_authenticate(owner)
    response = api.post("/api/v1/workspaces/", {"name": "Karachi Team"}, format="json")
    workspace = Workspace.objects.get(slug=response.json()["slug"])
    Project.objects.create(workspace=workspace, key="BAI", name="Baithak")
    return workspace


@pytest.fixture
def general(workspace: Workspace) -> Channel:
    return Channel.objects.for_workspace(workspace).get(name="general")


@pytest.fixture
def message(general: Channel, owner: User) -> Message:
    message, _ = messages.post(general, owner, "The upload button does nothing on Safari")
    return message


def from_message(api: APIClient, channel: Channel, seq: int | None, **body: Any) -> Any:
    return api.post(
        ISSUES,
        {"title": "Safari upload", "from_message": {"channel_id": channel.pk, "seq": seq}, **body},
        format="json",
    )


def test_an_issue_opened_from_a_message_links_both_ways(
    api: APIClient, general: Channel, message: Message
) -> None:
    response = from_message(api, general, message.seq)

    assert response.status_code == 201, response.json()
    assert response.json()["thread"] == {"channel": general.pk, "seq": message.seq}
    shown = api.get(f"{CHANNELS}{general.pk}/messages/").json()["messages"][-1]
    assert shown["issue"] == {"ref": "BAI-1", "project": "BAI", "number": 1}
    assert api.get(f"{ISSUES}1/").json()["thread"] == {"channel": general.pk, "seq": message.seq}


def test_the_message_gets_a_new_event_so_catch_up_brings_the_link(
    api: APIClient, general: Channel, message: Message
) -> None:
    before = message.event

    from_message(api, general, message.seq)

    caught = api.get(f"{CHANNELS}{general.pk}/messages/", {"after_event": before}).json()
    assert [m["issue"]["ref"] for m in caught["messages"] if m["issue"]] == ["BAI-1"]


def test_the_audit_log_names_the_message(
    api: APIClient, workspace: Workspace, general: Channel, message: Message
) -> None:
    from_message(api, general, message.seq)

    event = AuditEvent.objects.for_workspace(workspace).get(action="issue.create")
    assert event.changes["from_message"] == f"{general.pk}#{message.seq}"


def test_a_message_has_one_issue_at_most(
    api: APIClient, general: Channel, message: Message
) -> None:
    from_message(api, general, message.seq)

    again = from_message(api, general, message.seq)

    assert again.status_code == 400
    assert "BAI-1" in again.json()["from_message"][0]


def test_replies_and_deleted_messages_cannot_have_issues(
    api: APIClient, general: Channel, owner: User, message: Message
) -> None:
    reply, _ = messages.post(general, owner, "Same on iPad", parent=message, also_in_channel=True)
    gone, _ = messages.post(general, owner, "Never mind")
    messages.delete(gone)

    assert from_message(api, general, reply.seq).status_code == 400
    assert from_message(api, general, gone.seq).status_code == 400


def test_a_missing_message_is_404(api: APIClient, general: Channel) -> None:
    assert from_message(api, general, 999).status_code == 404


class TestPrivateChannels:
    @pytest.fixture
    def secret(self, workspace: Workspace, owner: User) -> Channel:
        channel = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE
        )
        ChannelMember.objects.create(channel=channel, user=owner)
        return channel

    @pytest.fixture
    def bilal(self, workspace: Workspace) -> User:
        user = make_user(username="bilal")
        Member.objects.create(workspace=workspace, user=user, role=Role.MEMBER)
        return user

    def test_a_message_in_a_channel_you_cannot_read_is_404(
        self, api: APIClient, secret: Channel, owner: User, bilal: User
    ) -> None:
        hidden, _ = messages.post(secret, owner, "Salaries for next year")
        api.force_authenticate(bilal)

        assert from_message(api, secret, hidden.seq).status_code == 404

    def test_the_thread_is_hidden_from_people_outside_the_channel(
        self, api: APIClient, secret: Channel, owner: User, bilal: User
    ) -> None:
        hidden, _ = messages.post(secret, owner, "Salaries for next year")
        from_message(api, secret, hidden.seq)
        api.force_authenticate(bilal)

        one = api.get(f"{ISSUES}1/").json()
        listed = api.get(ISSUES).json()["results"]

        assert one["thread"] is None
        assert [issue["thread"] for issue in listed] == [None]


class TestActivity:
    @pytest.fixture
    def linked(self, api: APIClient, general: Channel, message: Message) -> Message:
        from_message(api, general, message.seq)
        return message

    def thread(self, api: APIClient, channel: Channel, seq: int | None) -> list[dict[str, Any]]:
        response = api.get(f"{CHANNELS}{channel.pk}/messages/{seq}/replies/")
        return list(response.json()["replies"])

    def test_opening_is_said_in_the_thread(
        self, api: APIClient, general: Channel, linked: Message
    ) -> None:
        [line] = self.thread(api, general, linked.seq)

        assert (line["kind"], line["body"]) == ("activity", "opened BAI-1: Safari upload")
        assert line["seq"] is None

    def test_changes_go_to_the_thread_and_status_to_the_channel(
        self, api: APIClient, general: Channel, linked: Message
    ) -> None:
        api.patch(f"{ISSUES}1/", {"priority": "high"}, format="json")
        api.patch(f"{ISSUES}1/", {"status": "done"}, format="json")

        lines = self.thread(api, general, linked.seq)
        channel = api.get(f"{CHANNELS}{general.pk}/messages/").json()["messages"]

        assert [line["body"] for line in lines[1:]] == [
            "BAI-1: set priority to high",
            "BAI-1: moved it to Done",
        ]
        assert [line["seq"] is not None for line in lines[1:]] == [False, True]
        assert channel[-1]["body"] == "BAI-1: moved it to Done"

    def test_an_unchanged_patch_says_nothing(
        self, api: APIClient, general: Channel, linked: Message
    ) -> None:
        api.patch(f"{ISSUES}1/", {"title": "Safari upload"}, format="json")

        assert len(self.thread(api, general, linked.seq)) == 1

    def test_activity_names_nobody_and_cannot_be_edited(
        self, api: APIClient, workspace: Workspace, general: Channel, linked: Message
    ) -> None:
        bilal = make_user(username="bilal")
        Member.objects.create(workspace=workspace, user=bilal, role=Role.MEMBER)
        api.patch(f"{ISSUES}1/", {"title": "@bilal look"}, format="json")
        line = self.thread(api, general, linked.seq)[-1]

        edited = api.patch(
            f"{CHANNELS}{general.pk}/messages/{linked.seq}/replies/{line['thread_seq']}/",
            {"body": "something else"},
            format="json",
        )

        assert line["mentions"] == []
        assert edited.status_code == 403

    def test_an_archived_channel_gets_no_post(
        self, api: APIClient, general: Channel, owner: User
    ) -> None:
        topic, _ = messages.post(general, owner, "Old talk")
        general.archived_at = topic.created_at
        general.save(update_fields=["archived_at"])

        assert from_message(api, general, topic.seq).status_code == 201
        topic.refresh_from_db()
        assert topic.reply_count == 0

    def test_an_issue_without_a_message_posts_nowhere(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        response = api.post(ISSUES, {"title": "Standalone"}, format="json")
        api.patch(f"{ISSUES}1/", {"status": "done"}, format="json")

        assert response.status_code == 201
        assert not Message.objects.filter(kind="activity").exists()


def test_history_lists_every_change_oldest_first(api: APIClient, workspace: Workspace) -> None:
    api.post(ISSUES, {"title": "Standalone"}, format="json")
    api.patch(f"{ISSUES}1/", {"status": "in_progress", "description": "Steps"}, format="json")

    history = api.get(f"{ISSUES}1/history/").json()

    assert [row["lines"] for row in history] == [
        ["opened it"],
        ["edited the description", "moved it to In progress"],
    ]
    assert history[0]["actor"]["username"] == "owner"
