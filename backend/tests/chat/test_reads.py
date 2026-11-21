import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember
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


@pytest.fixture
def bilal(workspace: Workspace, general: Channel) -> User:
    user = make_user(username="bilal")
    Member.objects.create(workspace=workspace, user=user, role=Role.MEMBER)
    ChannelMember.objects.create(channel=general, user=user)
    return user


@pytest.fixture
def random(api: APIClient, owner: User, workspace: Workspace, bilal: User) -> Channel:
    """A public channel bilal made and owner is not in."""
    api.force_authenticate(bilal)
    api.post(BASE, {"name": "random"}, format="json")
    api.force_authenticate(owner)
    return Channel.objects.for_workspace(workspace).get(name="random")


def listed(api: APIClient, channel: Channel) -> dict[str, object]:
    found = [c for c in api.get(BASE).json() if c["id"] == channel.pk]
    return dict(found[0])


def mark(api: APIClient, channel: Channel, seq: object) -> tuple[int, dict[str, object]]:
    response = api.post(f"{BASE}{channel.pk}/read/", {"seq": seq}, format="json")
    return response.status_code, dict(response.json())


class TestCounting:
    def test_messages_from_others_are_unread(
        self, api: APIClient, general: Channel, bilal: User
    ) -> None:
        messages.post(general, bilal, "Salaam")
        messages.post(general, bilal, "Chai at four?")

        channel = listed(api, general)

        assert (channel["last_read_seq"], channel["unread"]) == (0, 2)

    def test_posting_marks_the_channel_read_for_the_author(
        self, api: APIClient, owner: User, general: Channel, bilal: User
    ) -> None:
        messages.post(general, bilal, "Salaam")
        messages.post(general, owner, "Walaikum salaam")

        channel = listed(api, general)

        assert (channel["last_read_seq"], channel["unread"]) == (2, 0)

    def test_deleted_messages_are_not_counted(
        self, api: APIClient, general: Channel, bilal: User
    ) -> None:
        messages.post(general, bilal, "Salaam")
        mistake, _ = messages.post(general, bilal, "Wrong channel")
        messages.delete(mistake)

        assert listed(api, general)["unread"] == 1

    def test_detail_carries_the_same_count(
        self, api: APIClient, general: Channel, bilal: User
    ) -> None:
        messages.post(general, bilal, "Salaam")

        body = api.get(f"{BASE}{general.pk}/").json()

        assert (body["last_read_seq"], body["unread"]) == (0, 1)

    def test_a_public_channel_read_from_outside_has_no_marker(
        self, api: APIClient, random: Channel, bilal: User
    ) -> None:
        messages.post(random, bilal, "Anyone here?")

        channel = listed(api, random)

        assert (channel["is_member"], channel["last_read_seq"], channel["unread"]) == (
            False,
            None,
            None,
        )

    def test_joining_starts_with_nothing_unread(
        self, api: APIClient, random: Channel, bilal: User
    ) -> None:
        for text in ("One", "Two", "Three"):
            messages.post(random, bilal, text)

        joined = api.post(f"{BASE}{random.pk}/join/").json()

        assert (joined["last_read_seq"], joined["unread"]) == (3, 0)


class TestMarking:
    def test_marking_moves_the_marker_and_returns_what_is_left(
        self, api: APIClient, general: Channel, bilal: User
    ) -> None:
        for text in ("One", "Two", "Three"):
            messages.post(general, bilal, text)

        status, body = mark(api, general, 2)

        assert status == 200
        assert body == {"channel": general.pk, "last_read_seq": 2, "unread": 1}

    def test_the_marker_never_moves_back(
        self, api: APIClient, general: Channel, bilal: User
    ) -> None:
        for text in ("One", "Two", "Three"):
            messages.post(general, bilal, text)
        mark(api, general, 3)

        status, body = mark(api, general, 1)

        assert (status, body["last_read_seq"], body["unread"]) == (200, 3, 0)

    def test_a_seq_past_the_end_stops_at_the_newest_message(
        self, api: APIClient, general: Channel, bilal: User
    ) -> None:
        messages.post(general, bilal, "One")

        _, body = mark(api, general, 99)

        assert body["last_read_seq"] == 1

    @pytest.mark.parametrize("seq", [-1, "soon", None])
    def test_a_bad_seq_is_refused(self, api: APIClient, general: Channel, seq: object) -> None:
        status, _ = mark(api, general, seq)

        assert status == 400

    def test_someone_not_in_the_channel_is_told_to_join(
        self, api: APIClient, random: Channel
    ) -> None:
        status, _ = mark(api, random, 0)

        assert status == 403
