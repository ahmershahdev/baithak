import itertools

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat.access import readable_channels
from apps.chat.models import Channel, ChannelMember
from apps.core.channels import ChannelKind, can_read
from apps.core.roles import Role
from apps.workspaces.models import AuditEvent, Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

CHANNELS = "/api/v1/workspaces/karachi-team/channels/"


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


def general(workspace: Workspace) -> Channel:
    return Channel.objects.for_workspace(workspace).get(name="general")


def make_channel(workspace: Workspace, name: str, kind: ChannelKind, *members: User) -> Channel:
    channel = Channel.objects.create(workspace=workspace, name=name, kind=kind)
    for user in members:
        ChannelMember.objects.create(channel=channel, user=user)
    return channel


def last_action(workspace: Workspace) -> str:
    event = AuditEvent.objects.for_workspace(workspace).order_by("-id").first()
    assert event is not None
    return event.action


def test_the_list_query_agrees_with_can_read_everywhere(workspace: Workspace) -> None:
    """readable_channels is can_read written as SQL; any drift would leak private channels."""
    people = {role: join(workspace, role, f"p-{role}") for role in Role}
    channels = {}
    for kind, with_member in itertools.product(ChannelKind, [False, True]):
        members = list(people.values()) if with_member else []
        channels[(kind, with_member)] = make_channel(
            workspace, f"{kind}-{int(with_member)}", kind, *members
        )

    for role, user in people.items():
        member = Member.objects.for_workspace(workspace).get(user=user)
        visible = set(readable_channels(member).values_list("pk", flat=True))
        for (kind, with_member), channel in channels.items():
            assert (channel.pk in visible) is can_read(role, kind, is_member=with_member), (
                role,
                kind,
                with_member,
            )


class TestDefaultChannel:
    def test_a_new_workspace_has_general_with_its_creator(
        self, owner: User, workspace: Workspace
    ) -> None:
        channel = general(workspace)

        assert channel.is_default
        assert channel.kind == ChannelKind.PUBLIC
        assert ChannelMember.objects.filter(channel=channel, user=owner).exists()

    def test_the_default_channel_cannot_be_archived(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        response = api.patch(
            f"{CHANNELS}{general(workspace).pk}/", {"archived": True}, format="json"
        )

        assert response.status_code == 403


class TestListing:
    def test_lists_public_channels_and_my_private_ones(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        bilal = join(workspace, Role.MEMBER, "bilal")
        make_channel(workspace, "random", ChannelKind.PUBLIC)
        make_channel(workspace, "mine", ChannelKind.PRIVATE, bilal)
        make_channel(workspace, "theirs", ChannelKind.PRIVATE, owner)
        api.force_authenticate(bilal)

        channels = api.get(CHANNELS).json()

        assert [(c["name"], c["is_member"]) for c in channels] == [
            ("general", False),
            ("mine", True),
            ("random", False),
        ]

    def test_guests_see_only_channels_they_were_added_to(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        guest = join(workspace, Role.GUEST, "guest")
        make_channel(workspace, "with-guest", ChannelKind.PUBLIC, guest)
        api.force_authenticate(guest)

        names = [c["name"] for c in api.get(CHANNELS).json()]

        assert names == ["with-guest"]


class TestCreating:
    def test_a_member_creates_a_channel_and_is_in_it(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        bilal = join(workspace, Role.MEMBER, "bilal")
        api.force_authenticate(bilal)

        response = api.post(
            CHANNELS, {"name": "#Design", "kind": "private", "topic": "Colors"}, format="json"
        )

        assert response.status_code == 201
        body = response.json()
        assert (body["name"], body["kind"], body["is_member"]) == ("design", "private", True)
        assert last_action(workspace) == "channel.create"

    def test_names_are_unique_in_a_workspace(self, api: APIClient, workspace: Workspace) -> None:
        response = api.post(CHANNELS, {"name": "general"}, format="json")

        assert response.status_code == 400
        assert response.json() == {"name": ["A channel with this name already exists."]}

    @pytest.mark.parametrize("name", ["", "-dash", "has space", "x" * 81, "Ünicode!"])
    def test_bad_names_are_rejected(self, api: APIClient, workspace: Workspace, name: str) -> None:
        response = api.post(CHANNELS, {"name": name}, format="json")

        assert response.status_code == 400

    def test_guests_cannot_create(self, api: APIClient, workspace: Workspace) -> None:
        api.force_authenticate(join(workspace, Role.GUEST, "guest"))

        response = api.post(CHANNELS, {"name": "nope"}, format="json")

        assert response.status_code == 403


class TestManaging:
    def test_the_creator_renames_and_sets_the_topic(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        bilal = join(workspace, Role.MEMBER, "bilal")
        api.force_authenticate(bilal)
        channel_id = api.post(CHANNELS, {"name": "design"}, format="json").json()["id"]

        response = api.patch(
            f"{CHANNELS}{channel_id}/", {"name": "brand", "topic": "Logo work"}, format="json"
        )

        assert response.status_code == 200
        assert (response.json()["name"], response.json()["topic"]) == ("brand", "Logo work")
        event = AuditEvent.objects.for_workspace(workspace).order_by("-id").first()
        assert event is not None
        assert event.changes == {"name": ["design", "brand"], "topic": ["", "Logo work"]}

    def test_other_members_cannot(self, api: APIClient, workspace: Workspace) -> None:
        api.force_authenticate(join(workspace, Role.MEMBER, "bilal"))
        channel = general(workspace)

        response = api.patch(f"{CHANNELS}{channel.pk}/", {"topic": "Mine now"}, format="json")

        assert response.status_code == 403

    def test_an_admin_archives_and_nobody_can_join_it(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        random = make_channel(workspace, "random", ChannelKind.PUBLIC)
        api.force_authenticate(join(workspace, Role.ADMIN, "admin"))

        archived = api.patch(f"{CHANNELS}{random.pk}/", {"archived": True}, format="json")
        api.force_authenticate(join(workspace, Role.MEMBER, "late"))
        joined = api.post(f"{CHANNELS}{random.pk}/join/")

        assert archived.json()["archived"] is True
        assert joined.status_code == 403

    def test_renaming_to_a_taken_name_is_400(self, api: APIClient, workspace: Workspace) -> None:
        random = make_channel(workspace, "random", ChannelKind.PUBLIC)

        response = api.patch(f"{CHANNELS}{random.pk}/", {"name": "general"}, format="json")

        assert response.status_code == 400

    def test_saving_without_changes_writes_no_audit_row(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        channel = general(workspace)
        before = AuditEvent.objects.for_workspace(workspace).count()

        api.patch(f"{CHANNELS}{channel.pk}/", {"topic": ""}, format="json")

        assert AuditEvent.objects.for_workspace(workspace).count() == before


class TestMembership:
    def test_joining_and_leaving_a_public_channel(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        bilal = join(workspace, Role.MEMBER, "bilal")
        random = make_channel(workspace, "random", ChannelKind.PUBLIC)
        api.force_authenticate(bilal)

        joined = api.post(f"{CHANNELS}{random.pk}/join/")
        again = api.post(f"{CHANNELS}{random.pk}/join/")
        left = api.post(f"{CHANNELS}{random.pk}/leave/")

        assert joined.json()["is_member"] is True
        assert again.status_code == 200
        assert left.status_code == 204
        assert not ChannelMember.objects.filter(channel=random, user=bilal).exists()
        assert last_action(workspace) == "channel.leave"

    def test_a_member_adds_someone_to_a_private_channel(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        bilal = join(workspace, Role.MEMBER, "bilal")
        secret = make_channel(workspace, "secret", ChannelKind.PRIVATE, owner)

        added = api.post(f"{CHANNELS}{secret.pk}/members/", {"user_id": bilal.pk}, format="json")
        twice = api.post(f"{CHANNELS}{secret.pk}/members/", {"user_id": bilal.pk}, format="json")
        api.force_authenticate(bilal)
        seen = api.get(f"{CHANNELS}{secret.pk}/members/").json()

        assert added.status_code == 201
        assert twice.status_code == 200
        assert [m["username"] for m in seen] == ["bilal", "owner"]
        assert last_action(workspace) == "channel.add_member"

    def test_people_outside_the_workspace_cannot_be_added(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        stranger = make_user(username="stranger")

        response = api.post(
            f"{CHANNELS}{general(workspace).pk}/members/", {"user_id": stranger.pk}, format="json"
        )

        assert response.status_code == 404

    def test_nobody_is_added_to_an_archived_channel(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        old = make_channel(workspace, "old", ChannelKind.PUBLIC, owner)
        api.patch(f"{CHANNELS}{old.pk}/", {"archived": True}, format="json")
        bilal = join(workspace, Role.MEMBER, "bilal")

        response = api.post(f"{CHANNELS}{old.pk}/members/", {"user_id": bilal.pk}, format="json")

        assert response.status_code == 403

    def test_guests_cannot_add_people(self, api: APIClient, workspace: Workspace) -> None:
        guest = join(workspace, Role.GUEST, "guest")
        room = make_channel(workspace, "room", ChannelKind.PUBLIC, guest)
        api.force_authenticate(guest)

        response = api.post(f"{CHANNELS}{room.pk}/members/", {"user_id": guest.pk}, format="json")

        assert response.status_code == 403

    def test_leaving_a_channel_you_are_not_in_does_nothing(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        random = make_channel(workspace, "random", ChannelKind.PUBLIC)
        before = AuditEvent.objects.for_workspace(workspace).count()

        response = api.post(f"{CHANNELS}{random.pk}/leave/")

        assert response.status_code == 204
        assert AuditEvent.objects.for_workspace(workspace).count() == before


@pytest.mark.parametrize(("role", "joins"), [(Role.MEMBER, True), (Role.GUEST, False)])
def test_new_members_join_the_default_channel_but_guests_do_not(
    workspace: Workspace, role: Role, joins: bool
) -> None:
    from apps.chat.services import join_default_channels

    newcomer = join(workspace, role, "newcomer")

    join_default_channels(workspace, newcomer, role)
    join_default_channels(workspace, newcomer, role)

    assert ChannelMember.objects.filter(channel=general(workspace), user=newcomer).count() == (
        1 if joins else 0
    )


def test_reading_one_channel(api: APIClient, workspace: Workspace) -> None:
    response = api.get(f"{CHANNELS}{general(workspace).pk}/")

    assert response.status_code == 200
    assert (response.json()["name"], response.json()["is_member"]) == ("general", True)
