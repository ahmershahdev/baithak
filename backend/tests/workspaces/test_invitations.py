import re
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.roles import Role
from apps.workspaces.invitations import hash_token, mask_email
from apps.workspaces.models import AuditEvent, Invitation, Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

INVITES = "/api/v1/workspaces/karachi-team/invitations/"


@pytest.fixture
def owner() -> User:
    return make_user(username="owner", display_name="Sana Owner")


@pytest.fixture
def workspace(owner: User) -> Workspace:
    workspace = Workspace.objects.create(name="Karachi Team", slug="karachi-team")
    Member.objects.create(workspace=workspace, user=owner, role=Role.OWNER)
    return workspace


def join(workspace: Workspace, role: Role, username: str) -> User:
    user = make_user(username=username)
    Member.objects.create(workspace=workspace, user=user, role=role)
    return user


def invite(
    api: APIClient, email: str = "Bilal@Example.com", role: str = "member"
) -> tuple[int, dict[str, object]]:
    response = api.post(INVITES, {"email": email, "role": role}, format="json")
    return response.status_code, response.json()


def token_from_last_email() -> str:
    match = re.search(r"/invite\?token=([\w-]+)", str(mail.outbox[-1].body))
    assert match is not None
    return match.group(1)


def actions(workspace: Workspace) -> list[str]:
    events = AuditEvent.objects.for_workspace(workspace).order_by("id")
    return list(events.values_list("action", flat=True))


class TestInviting:
    def test_admin_invites_by_email_and_it_is_audited(
        self,
        api: APIClient,
        owner: User,
        workspace: Workspace,
        django_capture_on_commit_callbacks: object,
    ) -> None:
        api.force_authenticate(owner)

        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            status, body = invite(api)

        assert status == 201
        assert body["email"] == "bilal@example.com"
        assert body["role"] == "member"
        assert mail.outbox[0].to == ["bilal@example.com"]
        assert mail.outbox[0].subject == "Sana Owner invited you to Karachi Team on Baithak"
        assert actions(workspace) == ["invitation.create"]

    def test_only_the_hash_of_the_token_is_stored(
        self,
        api: APIClient,
        owner: User,
        workspace: Workspace,
        django_capture_on_commit_callbacks: object,
    ) -> None:
        api.force_authenticate(owner)
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            invite(api)

        token = token_from_last_email()
        stored = Invitation.objects.for_workspace(workspace).get()

        assert stored.token_hash == hash_token(token)
        assert token not in stored.token_hash

    def test_inviting_again_replaces_the_old_invitation(
        self,
        api: APIClient,
        owner: User,
        workspace: Workspace,
        django_capture_on_commit_callbacks: object,
    ) -> None:
        api.force_authenticate(owner)
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            invite(api)
        first = token_from_last_email()
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            invite(api, role="guest")

        pending = api.get(INVITES).json()
        preview = api.post("/api/v1/invitations/preview/", {"token": first}, format="json")

        assert [(i["email"], i["role"]) for i in pending] == [("bilal@example.com", "guest")]
        assert preview.status_code == 404

    def test_someone_already_in_the_workspace_is_not_invited(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        join(workspace, Role.MEMBER, "bilal")
        api.force_authenticate(owner)

        status, body = invite(api, email="bilal@example.com")

        assert status == 400
        assert body == {"detail": "This person is already in the workspace."}

    @pytest.mark.parametrize("role", [Role.MEMBER, Role.GUEST])
    def test_members_and_guests_cannot_invite(
        self, api: APIClient, workspace: Workspace, role: Role
    ) -> None:
        api.force_authenticate(join(workspace, role, "someone"))

        status, _ = invite(api)

        assert status == 403
        assert Invitation.objects.count() == 0

    def test_owner_role_cannot_be_given_by_invitation(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        api.force_authenticate(owner)

        status, body = invite(api, role="owner")

        assert status == 400
        assert "role" in body

    def test_revoking_ends_the_link_and_is_audited(
        self,
        api: APIClient,
        owner: User,
        workspace: Workspace,
        django_capture_on_commit_callbacks: object,
    ) -> None:
        api.force_authenticate(owner)
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            _, body = invite(api)
        token = token_from_last_email()

        revoked = api.delete(f"{INVITES}{body['id']}/")
        again = api.delete(f"{INVITES}{body['id']}/")
        preview = api.post("/api/v1/invitations/preview/", {"token": token}, format="json")

        assert revoked.status_code == 204
        assert again.status_code == 404
        assert preview.status_code == 404
        assert actions(workspace)[-1] == "invitation.revoke"

    def test_invitations_of_another_workspace_cannot_be_revoked(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        other = Workspace.objects.create(name="Other", slug="other")
        theirs = Invitation.objects.create(
            workspace=other,
            email="x@example.com",
            role=Role.MEMBER,
            expires_at=timezone.now() + timedelta(days=1),
        )
        api.force_authenticate(owner)

        response = api.delete(f"{INVITES}{theirs.pk}/")

        assert response.status_code == 404
        theirs.refresh_from_db()
        assert theirs.revoked_at is None


class TestAccepting:
    @pytest.fixture
    def token(
        self,
        api: APIClient,
        owner: User,
        workspace: Workspace,
        django_capture_on_commit_callbacks: object,
    ) -> str:
        api.force_authenticate(owner)
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            invite(api, email="bilal@example.com", role="admin")
        api.force_authenticate(None)
        return token_from_last_email()

    def test_preview_shows_what_the_link_is_for(self, api: APIClient, token: str) -> None:
        response = api.post("/api/v1/invitations/preview/", {"token": token}, format="json")

        assert response.json() == {
            "workspace": "Karachi Team",
            "role": "admin",
            "invited_by": "owner",
            "email": "b***@example.com",
        }

    def test_the_invited_person_joins_with_the_role(
        self, api: APIClient, workspace: Workspace, token: str
    ) -> None:
        bilal = make_user(username="bilal", email="bilal@example.com")
        api.force_authenticate(bilal)

        response = api.post("/api/v1/invitations/accept/", {"token": token}, format="json")

        assert response.status_code == 200
        assert response.json()["slug"] == "karachi-team"
        assert Member.objects.for_workspace(workspace).get(user=bilal).role == Role.ADMIN
        assert actions(workspace)[-2:] == ["invitation.accept", "member.add"]

    def test_the_link_works_once(self, api: APIClient, token: str) -> None:
        api.force_authenticate(make_user(username="bilal", email="bilal@example.com"))

        first = api.post("/api/v1/invitations/accept/", {"token": token}, format="json")
        second = api.post("/api/v1/invitations/accept/", {"token": token}, format="json")

        assert first.status_code == 200
        assert second.status_code == 404

    def test_someone_with_another_email_cannot_use_it(
        self, api: APIClient, workspace: Workspace, token: str
    ) -> None:
        stranger = make_user(username="stranger", email="stranger@example.com")
        api.force_authenticate(stranger)

        response = api.post("/api/v1/invitations/accept/", {"token": token}, format="json")

        assert response.status_code == 403
        assert not Member.objects.for_workspace(workspace).filter(user=stranger).exists()

    def test_accepting_confirms_the_email(self, api: APIClient, token: str) -> None:
        bilal = make_user(username="bilal", email="bilal@example.com", email_verified_at=None)
        api.force_authenticate(bilal)

        api.post("/api/v1/invitations/accept/", {"token": token}, format="json")

        bilal.refresh_from_db()
        assert bilal.email_verified

    def test_expired_links_do_nothing(
        self, api: APIClient, workspace: Workspace, token: str
    ) -> None:
        Invitation.objects.for_workspace(workspace).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        api.force_authenticate(make_user(username="bilal", email="bilal@example.com"))

        accepted = api.post("/api/v1/invitations/accept/", {"token": token}, format="json")
        preview = api.post("/api/v1/invitations/preview/", {"token": token}, format="json")

        assert accepted.status_code == 404
        assert preview.status_code == 404

    def test_already_a_member_just_uses_up_the_link(
        self, api: APIClient, workspace: Workspace, token: str
    ) -> None:
        bilal = join(workspace, Role.GUEST, "bilal")
        bilal.email = "bilal@example.com"
        bilal.save(update_fields=["email"])
        api.force_authenticate(bilal)

        response = api.post("/api/v1/invitations/accept/", {"token": token}, format="json")

        assert response.status_code == 200
        assert Member.objects.for_workspace(workspace).get(user=bilal).role == Role.GUEST

    def test_accepting_needs_sign_in(self, api: APIClient, token: str) -> None:
        response = api.post("/api/v1/invitations/accept/", {"token": token}, format="json")

        assert response.status_code == 403

    @pytest.mark.parametrize("token", ["", "made-up"])
    def test_unknown_tokens_are_404(self, api: APIClient, token: str) -> None:
        response = api.post("/api/v1/invitations/preview/", {"token": token}, format="json")

        assert response.status_code in (400, 404)


def test_email_task_skips_invitations_that_are_no_longer_pending(owner: User) -> None:
    from apps.workspaces.tasks import send_invitation_email

    workspace = Workspace.objects.create(name="W", slug="w")
    gone = Invitation.objects.create(
        workspace=workspace,
        email="x@example.com",
        role=Role.MEMBER,
        expires_at=timezone.now() + timedelta(days=1),
        revoked_at=timezone.now(),
    )

    send_invitation_email(gone.pk)
    send_invitation_email(999999)

    assert mail.outbox == []


def test_masked_email_keeps_only_the_first_letter() -> None:
    assert mask_email("amna.khan@example.com") == "a***@example.com"


def test_members_cannot_revoke(api: APIClient, owner: User, workspace: Workspace) -> None:
    pending = Invitation.objects.create(
        workspace=workspace,
        email="x@example.com",
        role=Role.MEMBER,
        invited_by=owner,
        expires_at=timezone.now() + timedelta(days=1),
    )
    api.force_authenticate(join(workspace, Role.MEMBER, "member"))

    response = api.delete(f"{INVITES}{pending.pk}/")

    assert response.status_code == 403
