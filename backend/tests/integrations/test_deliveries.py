import hashlib
import hmac
import json
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from celery.exceptions import Retry
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chat.models import Channel, Message
from apps.core.roles import Role
from apps.core.webhooks import MAX_ATTEMPTS
from apps.integrations import deliveries, tasks
from apps.integrations.models import Webhook, WebhookDelivery
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user
from tests.integrations.conftest import WEBHOOKS

pytestmark = pytest.mark.django_db

PULL = {
    "action": "opened",
    "sender": {"login": "amna"},
    "repository": {"full_name": "team/app"},
    "pull_request": {
        "number": 12,
        "title": "Fix uploads",
        "html_url": "https://github.com/team/app/pull/12",
    },
}


@pytest.fixture
def github(api: APIClient, general: Channel) -> dict[str, Any]:
    made = api.post(
        WEBHOOKS, {"kind": "github", "channel_id": general.pk, "repo": "team/app"}, format="json"
    )
    return dict(made.json())


def deliver(hook: dict[str, Any], payload: Any, event: str = "pull_request", key: str = "") -> Any:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    signature = hmac.new((key or hook["secret"]).encode(), body.encode(), hashlib.sha256)
    return APIClient().generic(
        "POST",
        hook["url"].removeprefix("http://web.test"),
        body,
        content_type="application/json",
        HTTP_X_GITHUB_EVENT=event,
        HTTP_X_HUB_SIGNATURE_256="sha256=" + signature.hexdigest(),
        HTTP_X_GITHUB_DELIVERY="guid-1",
    )


def logged() -> list[tuple[str, str, str]]:
    return [(d.event, d.status, d.detail) for d in WebhookDelivery.objects.order_by("pk")]


class TestTheLog:
    def test_a_posted_delivery_links_its_message(self, github: dict[str, Any]) -> None:
        deliver(github, PULL)

        delivery = WebhookDelivery.objects.get()
        assert (delivery.status, delivery.attempts, delivery.text) == ("posted", 1, "")
        assert delivery.message == Message.objects.get(kind="integration")
        assert delivery.external_id == "guid-1"

    def test_what_was_not_posted_says_why(self, github: dict[str, Any]) -> None:
        deliver(github, {}, event="ping")
        deliver(github, {**PULL, "repository": {"full_name": "someone/else"}})
        deliver(github, PULL, event="push")
        deliver(github, "not json")

        assert logged() == [
            ("ping", "ignored", "Connected."),
            ("pull_request", "ignored", "Another repository."),
            ("push", "ignored", "Not an event that is posted."),
            ("pull_request", "failed", "Not JSON."),
        ]

    def test_unsigned_calls_are_not_logged(self, github: dict[str, Any]) -> None:
        assert deliver(github, PULL, key="guess").status_code == 401
        assert logged() == []

    def test_incoming_problems_are_logged(self, api: APIClient, general: Channel) -> None:
        hook = api.post(
            WEBHOOKS, {"kind": "incoming", "channel_id": general.pk, "name": "Bot"}, format="json"
        ).json()
        path = hook["url"].removeprefix("http://web.test")
        APIClient().post(path, {"text": ""}, format="json")
        general.archived_at = timezone.now()
        general.save(update_fields=["archived_at"])
        APIClient().post(path, {"text": "hi"}, format="json")

        assert logged() == [
            ("message", "failed", "No usable text."),
            ("message", "ignored", "The channel is archived."),
        ]

    def test_admins_read_the_latest_first_and_members_cannot(
        self, api: APIClient, workspace: Workspace, github: dict[str, Any]
    ) -> None:
        deliver(github, {}, event="ping")
        deliver(github, PULL)
        url = f"{WEBHOOKS}{github['id']}/deliveries/"

        rows = api.get(url).json()
        bilal = make_user(username="bilal")
        Member.objects.create(workspace=workspace, user=bilal, role=Role.MEMBER)
        api.force_authenticate(bilal)

        assert [(r["event"], r["status"]) for r in rows] == [
            ("pull_request", "posted"),
            ("ping", "ignored"),
        ]
        assert api.get(url).status_code == 403


class TestRetrying:
    @pytest.fixture
    def pending(self, github: dict[str, Any]) -> WebhookDelivery:
        webhook = Webhook.objects.get()
        return WebhookDelivery.objects.create(
            workspace_id=webhook.workspace_id, webhook=webhook, event="pull_request", text="Hi"
        )

    def test_a_failure_is_noted_and_tried_again(self, pending: WebhookDelivery) -> None:
        with mock.patch("apps.chat.messages.post", side_effect=RuntimeError("down")):
            again = deliveries.attempt(pending)

        pending.refresh_from_db()
        assert again
        assert (pending.status, pending.attempts, pending.detail) == (
            "pending",
            1,
            "RuntimeError: down",
        )

    def test_the_last_failure_gives_up(self, pending: WebhookDelivery) -> None:
        pending.attempts = MAX_ATTEMPTS - 1

        with mock.patch("apps.chat.messages.post", side_effect=RuntimeError("down")):
            again = deliveries.attempt(pending)

        pending.refresh_from_db()
        assert not again
        assert (pending.status, pending.attempts) == ("failed", MAX_ATTEMPTS)
        assert pending.finished_at is not None

    def test_the_task_schedules_the_retry_with_back_off(self, pending: WebhookDelivery) -> None:
        with (
            mock.patch("apps.chat.messages.post", side_effect=RuntimeError("down")),
            mock.patch.object(tasks.deliver, "retry", side_effect=Retry) as retry,
            pytest.raises(Retry),
        ):
            tasks.deliver.run(pending.pk)

        retry.assert_called_once_with(countdown=30)

    def test_a_retry_finds_the_channel_archived_meanwhile(
        self, pending: WebhookDelivery, general: Channel
    ) -> None:
        general.archived_at = timezone.now()
        general.save(update_fields=["archived_at"])

        tasks.deliver.run(pending.pk)

        pending.refresh_from_db()
        assert (pending.status, pending.detail) == ("ignored", "The channel is archived.")

    def test_a_finished_delivery_is_not_posted_again(self, pending: WebhookDelivery) -> None:
        tasks.deliver.run(pending.pk)
        tasks.deliver.run(pending.pk)

        assert Message.objects.filter(kind="integration").count() == 1


def test_old_finished_deliveries_are_pruned(github: dict[str, Any]) -> None:
    webhook = Webhook.objects.get()
    old = timezone.now() - timedelta(days=31)
    for status, finished in [("posted", old), ("posted", timezone.now()), ("pending", None)]:
        WebhookDelivery.objects.create(
            workspace_id=webhook.workspace_id,
            webhook=webhook,
            event="x",
            status=status,
            finished_at=finished,
        )

    tasks.prune_deliveries()

    assert sorted(WebhookDelivery.objects.values_list("status", flat=True)) == [
        "pending",
        "posted",
    ]
