from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.roles import Role
from apps.notifications.models import Notification
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user
from tests.issues.team import karachi_team

pytestmark = pytest.mark.django_db

ISSUES = "/api/v1/workspaces/karachi-team/projects/BAI/issues/"
NOTIFICATIONS = "/api/v1/workspaces/karachi-team/notifications/"


@pytest.fixture
def owner() -> User:
    return make_user(username="owner")


@pytest.fixture
def workspace(api: APIClient, owner: User) -> Workspace:
    return karachi_team(api, owner)


def join(workspace: Workspace, username: str) -> User:
    user = make_user(username=username)
    Member.objects.create(workspace=workspace, user=user, role=Role.MEMBER)
    return user


@pytest.fixture
def bilal(workspace: Workspace) -> User:
    return join(workspace, "bilal")


def mine(api: APIClient, user: User) -> Any:
    api.force_authenticate(user)
    return api.get(NOTIFICATIONS).json()


def test_assigning_someone_tells_them(api: APIClient, owner: User, bilal: User) -> None:
    api.post(ISSUES, {"title": "Fix uploads", "assignee_id": bilal.pk}, format="json")

    page = mine(api, bilal)

    assert page["unread"] == 1
    [item] = page["results"]
    assert item["kind"] == "assigned"
    assert item["issue"] == {"ref": "BAI-1", "project": "BAI", "number": 1, "title": "Fix uploads"}
    assert item["actor"]["username"] == "owner"
    assert (item["channel"], item["message"]) == (None, None)


def test_assigning_yourself_or_changing_nothing_tells_nobody(
    api: APIClient, owner: User, bilal: User
) -> None:
    api.post(ISSUES, {"title": "Mine", "assignee_id": owner.pk}, format="json")
    api.patch(f"{ISSUES}1/", {"assignee_id": bilal.pk}, format="json")
    api.patch(f"{ISSUES}1/", {"title": "Still Bilal's"}, format="json")

    assert mine(api, owner)["unread"] == 0
    assert mine(api, bilal)["unread"] == 1


def test_reassigning_takes_back_the_unread_notice(
    api: APIClient, workspace: Workspace, owner: User, bilal: User
) -> None:
    sana = join(workspace, "sana")
    api.post(ISSUES, {"title": "Fix uploads", "assignee_id": bilal.pk}, format="json")

    api.patch(f"{ISSUES}1/", {"assignee_id": sana.pk}, format="json")

    assert mine(api, bilal)["results"] == []
    assert mine(api, sana)["unread"] == 1


def test_a_read_notice_stays_after_reassigning(
    api: APIClient, workspace: Workspace, owner: User, bilal: User
) -> None:
    api.post(ISSUES, {"title": "Fix uploads", "assignee_id": bilal.pk}, format="json")
    api.force_authenticate(bilal)
    api.post(f"{NOTIFICATIONS}read/", {"all": True}, format="json")
    api.force_authenticate(owner)

    api.patch(f"{ISSUES}1/", {"assignee_id": None}, format="json")

    assert len(mine(api, bilal)["results"]) == 1


def test_someone_made_a_guest_no_longer_sees_issue_notices(
    api: APIClient, workspace: Workspace, bilal: User
) -> None:
    api.post(ISSUES, {"title": "Fix uploads", "assignee_id": bilal.pk}, format="json")
    Member.objects.filter(workspace=workspace, user=bilal).update(role=Role.GUEST)

    page = mine(api, bilal)

    assert (page["unread"], page["results"]) == (0, [])
    assert Notification.objects.filter(user=bilal).count() == 1
