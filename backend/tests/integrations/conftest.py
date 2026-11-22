from collections.abc import Callable
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat.models import Channel
from apps.integrations import tasks
from apps.workspaces.models import Workspace
from tests.accounts.factories import make_user

WEBHOOKS = "/api/v1/workspaces/karachi-team/integrations/webhooks/"


@pytest.fixture(autouse=True)
def _deliver_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests run in one transaction that never commits, so queued work would never start;
    here it starts at once (the task itself runs eagerly in test settings)."""

    def at_once(work: Callable[[], object]) -> None:
        work()

    monkeypatch.setattr(tasks, "transaction", SimpleNamespace(on_commit=at_once))


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
