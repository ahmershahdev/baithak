import hashlib
import hmac
import json
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat.models import Channel, ChannelMember, Message
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.integrations.models import Webhook
from apps.workspaces.models import AuditEvent, Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

WEBHOOKS = "/api/v1/workspaces/karachi-team/integrations/webhooks/"


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


def connect(api: APIClient, channel: Channel, repo: str = "Team/App") -> Any:
    return api.post(
        WEBHOOKS, {"kind": "github", "channel_id": channel.pk, "repo": repo}, format="json"
    )


class TestConnecting:
    def test_an_admin_connects_a_repo_and_sees_the_secret_once(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        made = connect(api, general, "https://github.com/Team/App/")
        listed = api.get(WEBHOOKS).json()

        assert made.status_code == 201, made.json()
        body = made.json()
        assert body["repo"] == "team/app"
        assert body["url"].startswith("http://web.test/api/v1/hooks/github/")
        assert len(body["secret"]) > 30
        assert [hook["repo"] for hook in listed] == ["team/app"]
        assert "secret" not in listed[0]
        assert AuditEvent.objects.for_workspace(workspace).filter(action="webhook.create").exists()

    def test_members_cannot_manage_webhooks(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        bilal = make_user(username="bilal")
        Member.objects.create(workspace=workspace, user=bilal, role=Role.MEMBER)
        api.force_authenticate(bilal)

        assert api.get(WEBHOOKS).status_code == 403
        assert connect(api, general).status_code == 403

    def test_a_bad_repo_name_is_refused(self, api: APIClient, general: Channel) -> None:
        assert connect(api, general, "not a repo").status_code == 400

    def test_a_private_channel_the_admin_is_not_in_is_404(
        self, api: APIClient, workspace: Workspace
    ) -> None:
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE
        )
        admin = make_user(username="admin")
        Member.objects.create(workspace=workspace, user=admin, role=Role.ADMIN)
        api.force_authenticate(admin)

        assert connect(api, secret).status_code == 404

    def test_an_archived_channel_is_refused(self, api: APIClient, general: Channel) -> None:
        general.archived_at = general.created_at
        general.save(update_fields=["archived_at"])

        assert connect(api, general).status_code == 400

    def test_removing_one_is_audited(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        hook = connect(api, general).json()

        assert api.delete(f"{WEBHOOKS}{hook['id']}/").status_code == 204
        assert not Webhook.objects.exists()
        assert AuditEvent.objects.for_workspace(workspace).filter(action="webhook.delete").exists()


def pull_opened(repo: str = "Team/App") -> dict[str, Any]:
    return {
        "action": "opened",
        "sender": {"login": "amna"},
        "repository": {"full_name": repo},
        "pull_request": {
            "number": 12,
            "title": "Fix uploads",
            "html_url": "https://github.com/team/app/pull/12",
        },
    }


class TestDeliveries:
    @pytest.fixture
    def hook(self, api: APIClient, general: Channel) -> dict[str, Any]:
        hook = dict(connect(api, general).json())
        api.force_authenticate(None)
        return hook

    def deliver(
        self,
        api: APIClient,
        hook: dict[str, Any],
        payload: Any,
        event: str = "pull_request",
        secret: str | None = None,
        delivery: str = "d-1",
    ) -> Any:
        body = json.dumps(payload).encode()
        key = (secret or hook["secret"]).encode()
        signature = "sha256=" + hmac.new(key, body, hashlib.sha256).hexdigest()
        # Like GitHub: no session and no CSRF token.
        return APIClient(enforce_csrf_checks=True).generic(
            "POST",
            hook["url"].removeprefix("http://web.test"),
            body.decode(),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT=event,
            HTTP_X_HUB_SIGNATURE_256=signature,
            HTTP_X_GITHUB_DELIVERY=delivery,
        )

    def test_a_signed_pull_request_is_posted_once_per_delivery(
        self, api: APIClient, hook: dict[str, Any], general: Channel
    ) -> None:
        first = self.deliver(api, hook, pull_opened())
        again = self.deliver(api, hook, pull_opened())

        assert (first.status_code, again.status_code) == (201, 201)
        [posted] = Message.objects.filter(channel=general, kind="integration")
        assert posted.author is None
        assert posted.sender_name == "GitHub"
        assert posted.body.startswith("amna opened pull request #12 in Team/App: Fix uploads")

    def test_a_wrong_signature_is_refused_before_reading(
        self, api: APIClient, hook: dict[str, Any]
    ) -> None:
        response = self.deliver(api, hook, pull_opened(), secret="guess")

        assert response.status_code == 401
        assert not Message.objects.filter(kind="integration").exists()

    def test_an_unknown_token_is_404(self, api: APIClient, hook: dict[str, Any]) -> None:
        hook = {**hook, "url": "http://web.test/api/v1/hooks/github/nope/"}

        assert self.deliver(api, hook, pull_opened()).status_code == 404

    def test_ping_answers_and_posts_nothing(self, api: APIClient, hook: dict[str, Any]) -> None:
        response = self.deliver(api, hook, {"zen": "Speak like a human."}, event="ping")

        assert response.status_code == 200
        assert not Message.objects.filter(kind="integration").exists()

    @pytest.mark.parametrize(
        ("event", "payload"),
        [
            ("push", pull_opened()),
            ("pull_request", pull_opened(repo="someone/else")),
            ("pull_request", {**pull_opened(), "action": "labeled"}),
        ],
    )
    def test_other_events_and_repos_are_ignored(
        self, api: APIClient, hook: dict[str, Any], event: str, payload: Any
    ) -> None:
        assert self.deliver(api, hook, payload, event=event).status_code == 202
        assert not Message.objects.filter(kind="integration").exists()

    def test_a_signed_body_that_is_not_json_is_400(
        self, api: APIClient, hook: dict[str, Any]
    ) -> None:
        body = b"not json"
        signature = "sha256=" + hmac.new(hook["secret"].encode(), body, hashlib.sha256).hexdigest()

        response = api.generic(
            "POST",
            hook["url"].removeprefix("http://web.test"),
            body.decode(),
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="pull_request",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        assert response.status_code == 400

    def test_an_archived_channel_gets_nothing(
        self, api: APIClient, hook: dict[str, Any], general: Channel
    ) -> None:
        general.archived_at = general.created_at
        general.save(update_fields=["archived_at"])

        assert self.deliver(api, hook, pull_opened()).status_code == 202

    def test_app_messages_name_nobody_and_tell_nobody(
        self, api: APIClient, hook: dict[str, Any], general: Channel, owner: User
    ) -> None:
        payload = {**pull_opened(), "pull_request": {**pull_opened()["pull_request"]}}
        payload["pull_request"]["title"] = "@owner please review"
        ChannelMember.objects.get_or_create(channel=general, user=owner)

        self.deliver(api, hook, payload)

        posted = Message.objects.get(kind="integration")
        assert list(posted.mentions.all()) == []
        assert not owner.notifications.exists()
