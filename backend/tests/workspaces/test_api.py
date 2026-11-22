from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat.models import Channel, ChannelMember
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
    assert response.status_code == 201
    return Workspace.objects.get(slug=response.json()["slug"])


def member_url(user: User) -> str:
    return f"/api/v1/workspaces/karachi-team/members/{user.pk}/"


def actions(workspace: Workspace) -> list[str]:
    return list(
        AuditEvent.objects.for_workspace(workspace).order_by("id").values_list("action", flat=True)
    )


class TestCreate:
    def test_creator_becomes_owner_and_it_is_audited(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        assert workspace.slug == "karachi-team"
        assert Member.objects.for_workspace(workspace).get().user == owner
        assert actions(workspace) == ["workspace.create", "member.add", "channel.create"]
        assert api.get("/api/v1/workspaces/").json() == [
            {
                "slug": "karachi-team",
                "name": "Karachi Team",
                "created_at": api.get("/api/v1/workspaces/karachi-team/").json()["created_at"],
                "role": "owner",
            }
        ]

    def test_same_name_gets_a_different_slug(self, api: APIClient, workspace: Workspace) -> None:
        second = api.post("/api/v1/workspaces/", {"name": "Karachi Team"}, format="json").json()

        assert second["slug"].startswith("karachi-team-")
        assert second["slug"] != workspace.slug

    def test_name_without_letters_still_gets_a_slug(self, api: APIClient, owner: User) -> None:
        api.force_authenticate(owner)

        response = api.post("/api/v1/workspaces/", {"name": "!!!"}, format="json")

        assert response.json()["slug"] == "workspace"

    def test_needs_a_confirmed_email(self, api: APIClient) -> None:
        api.force_authenticate(make_user(email_verified_at=None))

        response = api.post("/api/v1/workspaces/", {"name": "Team"}, format="json")

        assert response.status_code == 403
        assert response.json() == {"detail": "Confirm your email before creating a workspace."}
        assert Workspace.objects.count() == 0

    def test_blank_name_is_rejected(self, api: APIClient, owner: User) -> None:
        api.force_authenticate(owner)

        response = api.post("/api/v1/workspaces/", {"name": "   "}, format="json")

        assert response.status_code == 400

    def test_list_shows_only_my_workspaces(self, api: APIClient, workspace: Workspace) -> None:
        api.force_authenticate(make_user(username="other"))

        assert api.get("/api/v1/workspaces/").json() == []


class TestRename:
    def test_admin_renames_and_the_change_is_audited(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        api.force_authenticate(join(workspace, Role.ADMIN, "admin"))

        response = api.patch(
            "/api/v1/workspaces/karachi-team/", {"name": "Lahore Team"}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Lahore Team"
        event = AuditEvent.objects.for_workspace(workspace).first()
        assert event is not None
        assert event.action == "workspace.update"
        assert event.changes == {"name": ["Karachi Team", "Lahore Team"]}

    def test_same_name_writes_no_audit_row(self, api: APIClient, workspace: Workspace) -> None:
        api.patch("/api/v1/workspaces/karachi-team/", {"name": "Karachi Team"}, format="json")

        assert actions(workspace) == ["workspace.create", "member.add", "channel.create"]

    @pytest.mark.parametrize("role", [Role.MEMBER, Role.GUEST])
    def test_members_and_guests_cannot(
        self, api: APIClient, workspace: Workspace, role: Role
    ) -> None:
        api.force_authenticate(join(workspace, role, "someone"))

        response = api.patch("/api/v1/workspaces/karachi-team/", {"name": "X"}, format="json")

        assert response.status_code == 403
        workspace.refresh_from_db()
        assert workspace.name == "Karachi Team"


class TestMembers:
    def test_any_member_sees_the_list(self, api: APIClient, workspace: Workspace) -> None:
        api.force_authenticate(join(workspace, Role.GUEST, "guest"))

        members = api.get("/api/v1/workspaces/karachi-team/members/").json()

        assert [(m["username"], m["role"]) for m in members] == [
            ("guest", "guest"),
            ("owner", "owner"),
        ]
        assert "email" not in members[0]

    def test_admin_promotes_a_member_and_it_is_audited(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        api.force_authenticate(join(workspace, Role.ADMIN, "admin"))
        member = join(workspace, Role.MEMBER, "member")

        response = api.patch(
            member_url(member),
            {"role": "admin"},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["role"] == "admin"
        event = AuditEvent.objects.for_workspace(workspace).first()
        assert event is not None
        assert (event.action, event.changes) == ("member.update", {"role": ["member", "admin"]})

    def test_setting_the_same_role_writes_no_audit_row(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        member = join(workspace, Role.MEMBER, "member")
        before = actions(workspace)

        api.patch(
            member_url(member),
            {"role": "member"},
            format="json",
        )

        assert actions(workspace) == before

    def test_admin_cannot_make_an_owner(self, api: APIClient, workspace: Workspace) -> None:
        api.force_authenticate(join(workspace, Role.ADMIN, "admin"))
        member = join(workspace, Role.MEMBER, "member")

        response = api.patch(
            member_url(member),
            {"role": "owner"},
            format="json",
        )

        assert response.status_code == 403

    def test_last_owner_cannot_step_down(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        response = api.patch(member_url(owner), {"role": "admin"}, format="json")

        assert response.status_code == 403
        assert Member.objects.for_workspace(workspace).get(user=owner).role == Role.OWNER

    def test_unknown_role_is_rejected(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        response = api.patch(member_url(owner), {"role": "king"}, format="json")

        assert response.status_code == 400

    def test_member_leaves_and_it_is_audited(self, api: APIClient, workspace: Workspace) -> None:
        member = join(workspace, Role.MEMBER, "member")
        api.force_authenticate(member)

        response = api.delete(member_url(member))

        assert response.status_code == 204
        assert not Member.objects.for_workspace(workspace).filter(user=member).exists()
        assert actions(workspace)[-1] == "member.remove"
        assert api.get("/api/v1/workspaces/karachi-team/").status_code == 404

    def test_member_cannot_remove_someone_else(self, api: APIClient, workspace: Workspace) -> None:
        api.force_authenticate(join(workspace, Role.MEMBER, "member"))
        other = join(workspace, Role.MEMBER, "other")

        response = api.delete(member_url(other))

        assert response.status_code == 403

    def test_last_owner_cannot_leave(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        response = api.delete(member_url(owner))

        assert response.status_code == 403

    def test_unknown_member_is_404(self, api: APIClient, workspace: Workspace) -> None:
        response = api.delete("/api/v1/workspaces/karachi-team/members/999999/")

        assert response.status_code == 404


class TestBecomingAGuest:
    def test_leaves_every_channel_but_keeps_conversations(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        bilal = join(workspace, Role.MEMBER, "bilal")
        general = Channel.objects.for_workspace(workspace).get(name="general")
        ChannelMember.objects.create(channel=general, user=bilal)
        chat = Channel.objects.create(
            workspace=workspace, name=f"~{owner.pk}-{bilal.pk}", kind=ChannelKind.DIRECT
        )
        ChannelMember.objects.create(channel=chat, user=bilal)

        response = api.patch(member_url(bilal), {"role": "guest"}, format="json")

        assert response.status_code == 200
        kept = ChannelMember.objects.filter(user=bilal).values_list("channel_id", flat=True)
        assert list(kept) == [chat.pk]
        assert actions(workspace)[-2:] == ["member.update", "channel.remove_member"]

    def test_a_guest_made_a_member_joins_the_default_channel(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        guest = join(workspace, Role.GUEST, "guest")

        api.patch(member_url(guest), {"role": "member"}, format="json")

        rooms = ChannelMember.objects.filter(user=guest).values_list("channel__name", flat=True)
        assert list(rooms) == ["general"]


class TestAuditLog:
    def test_admin_reads_newest_first(self, api: APIClient, workspace: Workspace) -> None:
        api.force_authenticate(join(workspace, Role.ADMIN, "admin"))
        api.patch("/api/v1/workspaces/karachi-team/", {"name": "Renamed"}, format="json")

        page: dict[str, Any] = api.get("/api/v1/workspaces/karachi-team/audit/").json()

        assert [e["action"] for e in page["results"]] == [
            "workspace.update",
            "channel.create",
            "member.add",
            "workspace.create",
        ]
        assert page["results"][0]["actor"] == "admin"

    def test_members_cannot_read_it(self, api: APIClient, workspace: Workspace) -> None:
        api.force_authenticate(join(workspace, Role.MEMBER, "member"))

        assert api.get("/api/v1/workspaces/karachi-team/audit/").status_code == 403
