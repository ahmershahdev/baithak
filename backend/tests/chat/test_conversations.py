from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember
from apps.core.channels import ChannelKind
from apps.core.conversations import MAX_PEOPLE
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


def join(workspace: Workspace, username: str, role: Role = Role.MEMBER) -> User:
    user = make_user(username=username)
    Member.objects.create(workspace=workspace, user=user, role=role)
    return user


def start(api: APIClient, *people: User) -> Any:
    return api.post(f"{BASE}conversations/", {"user_ids": [p.pk for p in people]}, format="json")


class TestStarting:
    def test_a_direct_conversation_with_one_person(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        bilal = join(workspace, "bilal")

        response = start(api, bilal)

        assert response.status_code == 201
        body = response.json()
        assert (body["kind"], body["is_member"], body["unread"]) == ("direct", True, 0)
        assert [p["username"] for p in body["people"]] == ["bilal", "owner"]

    def test_the_same_people_open_the_same_conversation(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        bilal = join(workspace, "bilal")
        first = start(api, bilal).json()

        api.force_authenticate(bilal)
        owner = Member.objects.for_workspace(workspace).get(role=Role.OWNER).user
        again = start(api, owner)

        assert again.status_code == 200
        assert again.json()["id"] == first["id"]

    def test_three_or_more_make_a_group(self, api: APIClient, workspace: Workspace) -> None:
        bilal, sara = join(workspace, "bilal"), join(workspace, "sara")

        body = start(api, bilal, sara).json()

        assert body["kind"] == "group"
        assert len(body["people"]) == 3

    def test_a_guest_can_start_one_too(self, api: APIClient, workspace: Workspace) -> None:
        guest = join(workspace, "guest", Role.GUEST)
        bilal = join(workspace, "bilal")
        api.force_authenticate(guest)

        assert start(api, bilal).status_code == 201

    @pytest.mark.parametrize("others", [0, MAX_PEOPLE])
    def test_too_few_or_too_many_people_is_refused(
        self, api: APIClient, owner: User, workspace: Workspace, others: int
    ) -> None:
        people = [join(workspace, f"person{i}") for i in range(others)] or [owner]

        assert start(api, *people).status_code == 400

    def test_people_outside_the_workspace_are_refused(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        assert start(api, make_user(username="stranger")).status_code == 400

    def test_starting_one_is_audited_without_saying_who(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        start(api, join(workspace, "bilal"))

        event = AuditEvent.objects.for_workspace(workspace).order_by("-id").first()
        assert event is not None
        assert (event.action, event.changes) == (
            "conversation.create",
            {"kind": "direct", "people": 2},
        )

    def test_opening_it_again_brings_back_someone_who_left(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        bilal = join(workspace, "bilal")
        channel_id = start(api, bilal).json()["id"]
        ChannelMember.objects.filter(channel_id=channel_id, user=bilal).delete()

        start(api, bilal)

        assert ChannelMember.objects.filter(channel_id=channel_id, user=bilal).exists()


class TestPrivacy:
    def test_nobody_else_can_read_it_not_even_the_owner(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        bilal, sara = join(workspace, "bilal"), join(workspace, "sara")
        api.force_authenticate(bilal)
        channel_id = start(api, sara).json()["id"]

        owner = Member.objects.for_workspace(workspace).get(role=Role.OWNER).user
        api.force_authenticate(owner)

        assert api.get(f"{BASE}{channel_id}/").status_code == 404
        assert api.get(f"{BASE}{channel_id}/messages/").status_code == 404
        assert channel_id not in [c["id"] for c in api.get(BASE).json()]

    def test_it_cannot_be_renamed_archived_or_added_to(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        bilal, sara = join(workspace, "bilal"), join(workspace, "sara")
        channel_id = start(api, bilal).json()["id"]

        renamed = api.patch(f"{BASE}{channel_id}/", {"archived": True}, format="json")
        added = api.post(f"{BASE}{channel_id}/members/", {"user_id": sara.pk}, format="json")

        assert (renamed.status_code, added.status_code) == (403, 403)

    def test_a_channel_cannot_be_created_as_a_conversation(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        response = api.post(BASE, {"name": "sneaky", "kind": "direct"}, format="json")

        assert response.status_code == 400

    def test_messages_and_unread_work_as_in_channels(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        bilal = join(workspace, "bilal")
        channel = Channel.objects.get(pk=start(api, bilal).json()["id"])
        assert channel.kind == ChannelKind.DIRECT

        messages.post(channel, bilal, "Salaam")

        listed = next(c for c in api.get(BASE).json() if c["id"] == channel.pk)
        assert listed["unread"] == 1
