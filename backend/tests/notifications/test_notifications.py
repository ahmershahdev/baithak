from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember
from apps.chat.reads import mark_read
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.notifications.models import Notification
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

URL = "/api/v1/workspaces/karachi-team/notifications/"


@pytest.fixture
def workspace(api: APIClient) -> Workspace:
    founder = make_user(username="owner")
    api.force_authenticate(founder)
    response = api.post("/api/v1/workspaces/", {"name": "Karachi Team"}, format="json")
    return Workspace.objects.get(slug=response.json()["slug"])


@pytest.fixture
def owner(workspace: Workspace) -> User:
    return Member.objects.for_workspace(workspace).get(role=Role.OWNER).user


@pytest.fixture
def general(workspace: Workspace) -> Channel:
    return Channel.objects.for_workspace(workspace).get(is_default=True)


@pytest.fixture
def bilal(workspace: Workspace, general: Channel) -> User:
    user = make_user(username="bilal")
    Member.objects.create(workspace=workspace, user=user, role=Role.MEMBER)
    ChannelMember.objects.create(channel=general, user=user)
    return user


def mine(api: APIClient, user: User, **params: Any) -> Any:
    api.force_authenticate(user)
    response = api.get(URL, params)
    assert response.status_code == 200
    return response.json()


class TestWhoIsTold:
    def test_a_mention_tells_the_person_named(
        self, api: APIClient, owner: User, general: Channel, bilal: User
    ) -> None:
        messages.post(general, owner, "@bilal can you look?")

        page = mine(api, bilal)

        assert page["unread"] == 1
        hit = page["results"][0]
        assert (hit["kind"], hit["channel"], hit["read"]) == ("mention", general.pk, False)
        assert hit["message"]["body"] == "@bilal can you look?"
        assert mine(api, owner)["results"] == []

    def test_at_channel_tells_members_only(
        self, api: APIClient, owner: User, workspace: Workspace, general: Channel, bilal: User
    ) -> None:
        reader = make_user(username="reader")
        Member.objects.create(workspace=workspace, user=reader, role=Role.MEMBER)

        messages.post(general, owner, "@channel standup moved")

        assert mine(api, bilal)["results"][0]["kind"] == "channel"
        assert mine(api, reader)["results"] == []

    def test_a_direct_message_tells_the_other_person(
        self, api: APIClient, owner: User, workspace: Workspace, bilal: User
    ) -> None:
        api.force_authenticate(owner)
        channel_id = api.post(
            "/api/v1/workspaces/karachi-team/channels/conversations/",
            {"user_ids": [bilal.pk]},
            format="json",
        ).json()["id"]

        messages.post(Channel.objects.get(pk=channel_id), owner, "Salaam")

        assert mine(api, bilal)["results"][0]["kind"] == "direct"

    def test_a_plain_message_tells_nobody(
        self, api: APIClient, owner: User, general: Channel, bilal: User
    ) -> None:
        messages.post(general, owner, "Morning all")

        assert mine(api, bilal)["unread"] == 0

    def test_an_edit_tells_people_newly_named_once(
        self, api: APIClient, owner: User, workspace: Workspace, general: Channel, bilal: User
    ) -> None:
        sara = make_user(username="sara")
        Member.objects.create(workspace=workspace, user=sara, role=Role.MEMBER)
        message, _ = messages.post(general, owner, "@bilal look")

        messages.edit(message, "@bilal and @sara look")
        messages.edit(message, "@bilal and @sara, look now")

        assert Notification.objects.filter(message=message).count() == 2
        assert mine(api, sara)["results"][0]["kind"] == "mention"

    def test_deleting_the_message_takes_its_notifications(
        self, api: APIClient, owner: User, general: Channel, bilal: User
    ) -> None:
        message, _ = messages.post(general, owner, "@bilal oops")

        messages.delete(message)

        assert mine(api, bilal)["unread"] == 0


class TestReading:
    def test_reading_the_channel_reads_its_notifications(
        self, api: APIClient, owner: User, general: Channel, bilal: User
    ) -> None:
        messages.post(general, owner, "@bilal first")
        messages.post(general, owner, "@bilal second")

        mark_read(general, bilal.pk, 1)

        page = mine(api, bilal)
        assert page["unread"] == 1
        assert [n["read"] for n in page["results"]] == [False, True]

    def test_marking_some_or_all_read(
        self, api: APIClient, owner: User, general: Channel, bilal: User
    ) -> None:
        for text in ("@bilal one", "@bilal two", "@bilal three"):
            messages.post(general, owner, text)
        newest = mine(api, bilal)["results"][0]["id"]

        some = api.post(f"{URL}read/", {"ids": [newest]}, format="json").json()
        everything = api.post(f"{URL}read/", {"all": True}, format="json").json()

        assert (some["unread"], everything["unread"]) == (2, 0)

    def test_nobody_can_mark_someone_elses_read(
        self, api: APIClient, owner: User, general: Channel, bilal: User
    ) -> None:
        messages.post(general, owner, "@bilal yours")
        theirs = Notification.objects.get(user=bilal).pk

        api.force_authenticate(owner)
        api.post(f"{URL}read/", {"ids": [theirs]}, format="json")

        assert mine(api, bilal)["unread"] == 1

    def test_leaving_a_private_channel_hides_its_notifications(
        self, api: APIClient, owner: User, workspace: Workspace, bilal: User
    ) -> None:
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE, created_by=owner
        )
        ChannelMember.objects.create(channel=secret, user=owner)
        ChannelMember.objects.create(channel=secret, user=bilal)
        messages.post(secret, owner, "@bilal secret plan")
        ChannelMember.objects.filter(channel=secret, user=bilal).delete()

        page = mine(api, bilal)

        assert (page["unread"], page["results"]) == (0, [])

    def test_pages_go_back_in_time(
        self, api: APIClient, owner: User, general: Channel, bilal: User
    ) -> None:
        for number in range(32):
            messages.post(general, owner, f"@bilal note {number}")

        first = mine(api, bilal)
        second = mine(api, bilal, before_id=first["next"])

        assert len(first["results"]) == 30
        assert [n["message"]["body"] for n in second["results"]] == [
            "@bilal note 1",
            "@bilal note 0",
        ]
        assert second["next"] is None
