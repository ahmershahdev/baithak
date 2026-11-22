import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat.models import Channel
from apps.workspaces.models import Workspace
from tests.accounts.factories import make_user

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
