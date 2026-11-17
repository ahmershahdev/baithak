"""Every workspace endpoint, called by someone who can't see the workspace, answers 404.

AGENTS.md: a workspace, channel, message, file or issue the person can't see is 404, never 403.
New endpoints are added to ENDPOINTS; test_every_endpoint_is_listed fails until they are.
"""

from typing import Any

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.core.roles import Role
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

MEMBER = "/api/v1/workspaces/{slug}/members/{user_id}/"

# (url name, method, path with {slug} and {user_id}, body)
ENDPOINTS: list[tuple[str, str, str, dict[str, Any] | None]] = [
    ("workspaces:detail", "get", "/api/v1/workspaces/{slug}/", None),
    ("workspaces:detail", "patch", "/api/v1/workspaces/{slug}/", {"name": "Taken over"}),
    ("workspaces:members", "get", "/api/v1/workspaces/{slug}/members/", None),
    (
        "workspaces:member",
        "patch",
        "/api/v1/workspaces/{slug}/members/{user_id}/",
        {"role": "guest"},
    ),
    ("workspaces:member", "delete", "/api/v1/workspaces/{slug}/members/{user_id}/", None),
    ("workspaces:audit", "get", "/api/v1/workspaces/{slug}/audit/", None),
]

# Endpoints that are not inside one workspace, so the rule above does not apply.
NOT_WORKSPACE_SCOPED = {"workspaces:list"}


def _names(resolver: URLResolver, namespace: str = "") -> set[str]:
    names: set[str] = set()
    for entry in resolver.url_patterns:
        if isinstance(entry, URLResolver):
            inner = f"{namespace}{entry.namespace}:" if entry.namespace else namespace
            names |= _names(entry, inner)
        elif isinstance(entry, URLPattern) and entry.name:
            names.add(f"{namespace}{entry.name}")
    return names


def test_every_endpoint_is_listed() -> None:
    scoped = {name for name in _names(get_resolver()) if name.startswith("workspaces:")}
    assert scoped - NOT_WORKSPACE_SCOPED == {name for name, *_ in ENDPOINTS}


@pytest.fixture
def workspace() -> Workspace:
    owner = make_user(username="owner")
    workspace = Workspace.objects.create(name="Private", slug="private", created_by=owner)
    Member.objects.create(workspace=workspace, user=owner, role=Role.OWNER)
    return workspace


def _call(api: APIClient, method: str, path: str, body: dict[str, Any] | None) -> int:
    response = getattr(api, method)(path, body, format="json")
    return int(response.status_code)


@pytest.mark.parametrize(("name", "method", "path", "body"), ENDPOINTS)
def test_outsider_gets_404(
    api: APIClient, workspace: Workspace, name: str, method: str, path: str, body: Any
) -> None:
    api.force_authenticate(make_user(username="outsider"))
    owner_id = Member.objects.for_workspace(workspace).get().user_id

    status = _call(api, method, path.format(slug=workspace.slug, user_id=owner_id), body)

    assert status == 404


@pytest.mark.parametrize(("name", "method", "path", "body"), ENDPOINTS)
def test_unknown_workspace_gets_the_same_404(
    api: APIClient, workspace: Workspace, name: str, method: str, path: str, body: Any
) -> None:
    api.force_authenticate(make_user(username="outsider"))

    status = _call(api, method, path.format(slug="does-not-exist", user_id=1), body)

    assert status == 404


@pytest.mark.parametrize(("name", "method", "path", "body"), ENDPOINTS)
def test_signed_out_gets_403(
    api: APIClient, workspace: Workspace, name: str, method: str, path: str, body: Any
) -> None:
    status = _call(api, method, path.format(slug=workspace.slug, user_id=1), body)

    assert status == 403


def test_member_cannot_reach_a_person_in_another_workspace(
    api: APIClient, workspace: Workspace
) -> None:
    mine = Workspace.objects.create(name="Mine", slug="mine")
    me = make_user(username="me")
    Member.objects.create(workspace=mine, user=me, role=Role.OWNER)
    stranger = Member.objects.for_workspace(workspace).get()
    api.force_authenticate(me)

    path = f"/api/v1/workspaces/mine/members/{stranger.user_id}/"

    patched = api.patch(path, {"role": "guest"}, format="json")
    deleted = api.delete(path)

    assert patched.status_code == 404
    assert deleted.status_code == 404
    assert Member.objects.for_workspace(workspace).get().role == Role.OWNER
