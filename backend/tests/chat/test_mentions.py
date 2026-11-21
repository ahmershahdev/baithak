import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.workspaces.models import Member, Workspace
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


def join(workspace: Workspace, username: str, role: Role = Role.MEMBER) -> User:
    user = make_user(username=username)
    Member.objects.create(workspace=workspace, user=user, role=role)
    return user


def send(api: APIClient, channel: Channel, body: str) -> dict[str, object]:
    response = api.post(f"{BASE}{channel.pk}/messages/", {"body": body}, format="json")
    assert response.status_code == 201, response.json()
    return dict(response.json())


def handles(message: dict[str, object]) -> list[object]:
    mentioned = message["mentions"]
    assert isinstance(mentioned, list)
    return [m["username"] for m in mentioned]


class TestResolving:
    def test_members_named_in_the_body_are_mentioned(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        join(workspace, "amna")
        join(workspace, "bilal")

        sent = send(api, general, "@bilal and @Amna: chai?")

        assert handles(sent) == ["amna", "bilal"]
        assert sent["mentions_channel"] is False

    def test_unknown_handles_and_people_elsewhere_are_not(
        self, api: APIClient, general: Channel
    ) -> None:
        make_user(username="stranger")

        sent = send(api, general, "@nobody @stranger hello")

        assert handles(sent) == []

    def test_someone_who_cannot_read_a_private_channel_is_not_mentioned(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        join(workspace, "admin", Role.ADMIN)
        inside = join(workspace, "inside")
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE, created_by=owner
        )
        ChannelMember.objects.create(channel=secret, user=owner)
        ChannelMember.objects.create(channel=secret, user=inside)

        sent = send(api, secret, "@admin @inside look")

        assert handles(sent) == ["inside"]

    def test_a_guest_outside_a_public_channel_is_not_mentioned(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        join(workspace, "guest", Role.GUEST)

        assert handles(send(api, general, "@guest hi")) == []

    def test_a_member_can_mention_the_channel(self, api: APIClient, general: Channel) -> None:
        assert send(api, general, "@channel lunch")["mentions_channel"] is True

    def test_a_guest_cannot(self, api: APIClient, workspace: Workspace, general: Channel) -> None:
        guest = join(workspace, "guest", Role.GUEST)
        ChannelMember.objects.create(channel=general, user=guest)
        api.force_authenticate(guest)

        assert send(api, general, "@channel lunch")["mentions_channel"] is False


class TestChanging:
    def test_an_edit_works_the_mentions_out_again(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        join(workspace, "amna")
        join(workspace, "bilal")
        send(api, general, "@amna salaam")

        edited = api.patch(
            f"{BASE}{general.pk}/messages/1/", {"body": "@bilal salaam, @channel"}, format="json"
        ).json()

        assert handles(edited) == ["bilal"]
        assert edited["mentions_channel"] is True

    def test_deleting_removes_them(
        self, api: APIClient, owner: User, workspace: Workspace, general: Channel
    ) -> None:
        join(workspace, "amna")
        message, _ = messages.post(general, owner, "@amna @channel")

        messages.delete(message)

        message.refresh_from_db()
        assert (list(message.mentions.all()), message.mentions_channel) == ([], False)

    def test_replies_carry_mentions_too(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        join(workspace, "amna")
        send(api, general, "Question")

        reply = api.post(
            f"{BASE}{general.pk}/messages/1/replies/", {"body": "@amna knows"}, format="json"
        ).json()

        assert handles(reply) == ["amna"]

    def test_history_lists_mentions(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        join(workspace, "amna")
        send(api, general, "@amna one")
        send(api, general, "two")

        page = api.get(f"{BASE}{general.pk}/messages/").json()

        assert [handles(m) for m in page["messages"]] == [["amna"], []]
