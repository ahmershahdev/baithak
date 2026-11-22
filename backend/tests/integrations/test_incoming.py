from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.chat.models import Channel, Message
from apps.core.webhooks import digest
from apps.integrations.models import Webhook
from tests.integrations.conftest import WEBHOOKS

pytestmark = pytest.mark.django_db


def make(api: APIClient, channel: Channel, name: str = "Deploy bot") -> Any:
    return api.post(
        WEBHOOKS, {"kind": "incoming", "channel_id": channel.pk, "name": name}, format="json"
    )


@pytest.fixture
def hook(api: APIClient, general: Channel) -> dict[str, Any]:
    made = make(api, general)
    assert made.status_code == 201, made.json()
    return dict(made.json())


def send(hook: dict[str, Any], body: Any) -> Any:
    # Like any outside tool: no session and no CSRF token.
    return APIClient(enforce_csrf_checks=True).post(
        hook["url"].removeprefix("http://web.test"), body, format="json"
    )


class TestMaking:
    def test_the_url_is_shown_once_and_only_its_digest_is_kept(
        self, api: APIClient, hook: dict[str, Any]
    ) -> None:
        token = hook["url"].rstrip("/").rsplit("/", 1)[1]
        listed = api.get(WEBHOOKS).json()

        assert hook["url"].startswith("http://web.test/api/v1/hooks/incoming/")
        assert hook["secret"] is None
        assert listed[0]["name"] == "Deploy bot"
        assert listed[0]["url"] is None
        assert Webhook.objects.get().token == digest(token)

    def test_a_name_is_needed(self, api: APIClient, general: Channel) -> None:
        assert make(api, general, name="  ").status_code == 400

    def test_github_still_needs_a_repo(self, api: APIClient, general: Channel) -> None:
        response = api.post(WEBHOOKS, {"kind": "github", "channel_id": general.pk}, format="json")

        assert response.status_code == 400


class TestPosting:
    def test_text_is_posted_under_the_webhook_s_name(
        self, hook: dict[str, Any], general: Channel
    ) -> None:
        response = send(hook, {"text": "Deployed v1.2 to production"})

        assert response.status_code == 202
        posted = Message.objects.get(kind="integration")
        assert (posted.channel_id, posted.author, posted.sender_name, posted.body) == (
            general.pk,
            None,
            "Deploy bot",
            "Deployed v1.2 to production",
        )

    def test_a_wrong_url_is_404(self, hook: dict[str, Any]) -> None:
        wrong = {**hook, "url": "http://web.test/api/v1/hooks/incoming/guess/"}

        assert send(wrong, {"text": "hi"}).status_code == 404

    def test_the_stored_digest_does_not_work_as_a_url(self, hook: dict[str, Any]) -> None:
        stored = Webhook.objects.get().token
        leaked = {**hook, "url": f"http://web.test/api/v1/hooks/incoming/{stored}/"}

        assert send(leaked, {"text": "hi"}).status_code == 404

    @pytest.mark.parametrize("body", [{}, {"text": ""}, {"text": "x" * 4001}])
    def test_text_must_be_there_and_not_too_long(
        self, hook: dict[str, Any], body: dict[str, Any]
    ) -> None:
        assert send(hook, body).status_code == 400

    def test_an_archived_channel_says_so(self, hook: dict[str, Any], general: Channel) -> None:
        general.archived_at = general.created_at
        general.save(update_fields=["archived_at"])

        assert send(hook, {"text": "hi"}).status_code == 409
        assert not Message.objects.filter(kind="integration").exists()

    def test_each_webhook_is_rate_limited_on_its_own(
        self, api: APIClient, hook: dict[str, Any], general: Channel
    ) -> None:
        other = dict(make(api, general, name="Other bot").json())
        answers = [send(hook, {"text": f"n{i}"}).status_code for i in range(31)]

        assert answers[:30] == [202] * 30
        assert answers[30] == 429
        assert send(other, {"text": "still fine"}).status_code == 202
