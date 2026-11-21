"""Every workspace endpoint, called by someone who can't see the workspace, answers 404.

AGENTS.md: a workspace, channel, message, file or issue the person can't see is 404, never 403.
New endpoints are added to ENDPOINTS; test_every_endpoint_is_listed fails until they are.
"""

from typing import Any

import pytest
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from apps.chat.models import Channel, ChannelMember
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

MEMBER = "/api/v1/workspaces/{slug}/members/{user_id}/"
CHANNEL = "/api/v1/workspaces/{slug}/channels/{channel_id}/"
THUMBS_UP = "\U0001f44d"

# (url name, method, path with {slug}, {user_id} and {channel_id}, body)
ENDPOINTS: list[tuple[str, str, str, dict[str, Any] | None]] = [
    ("workspaces:detail", "get", "/api/v1/workspaces/{slug}/", None),
    ("workspaces:detail", "patch", "/api/v1/workspaces/{slug}/", {"name": "Taken over"}),
    ("workspaces:members", "get", "/api/v1/workspaces/{slug}/members/", None),
    ("workspaces:member", "patch", MEMBER, {"role": "guest"}),
    ("workspaces:member", "delete", MEMBER, None),
    ("workspaces:audit", "get", "/api/v1/workspaces/{slug}/audit/", None),
    ("workspaces:invitations", "get", "/api/v1/workspaces/{slug}/invitations/", None),
    (
        "workspaces:invitations",
        "post",
        "/api/v1/workspaces/{slug}/invitations/",
        {"email": "x@example.com", "role": "member"},
    ),
    ("workspaces:invitation", "delete", "/api/v1/workspaces/{slug}/invitations/1/", None),
    ("channels:list", "get", "/api/v1/workspaces/{slug}/channels/", None),
    ("channels:list", "post", "/api/v1/workspaces/{slug}/channels/", {"name": "taken"}),
    (
        "channels:conversations",
        "post",
        "/api/v1/workspaces/{slug}/channels/conversations/",
        {"user_ids": [1]},
    ),
    ("channels:detail", "get", CHANNEL, None),
    ("channels:detail", "patch", CHANNEL, {"topic": "Taken over"}),
    ("channels:join", "post", CHANNEL + "join/", None),
    ("channels:leave", "post", CHANNEL + "leave/", None),
    ("channels:read", "post", CHANNEL + "read/", {"seq": 1}),
    ("channels:members", "get", CHANNEL + "members/", None),
    ("channels:members", "post", CHANNEL + "members/", {"user_id": 1}),
    ("channels:messages", "get", CHANNEL + "messages/", None),
    ("channels:messages", "post", CHANNEL + "messages/", {"body": "Let me in"}),
    ("channels:message", "patch", CHANNEL + "messages/1/", {"body": "Changed"}),
    ("channels:message", "delete", CHANNEL + "messages/1/", None),
    ("channels:thread", "get", CHANNEL + "messages/1/replies/", None),
    ("channels:thread", "post", CHANNEL + "messages/1/replies/", {"body": "Me too"}),
    ("channels:reply", "patch", CHANNEL + "messages/1/replies/1/", {"body": "Changed"}),
    ("channels:reply", "delete", CHANNEL + "messages/1/replies/1/", None),
    ("channels:reactions", "post", CHANNEL + "messages/1/reactions/", {"emoji": THUMBS_UP}),
    ("channels:reaction", "delete", CHANNEL + "messages/1/reactions/%F0%9F%91%8D/", None),
    (
        "channels:reply_reactions",
        "post",
        CHANNEL + "messages/1/replies/1/reactions/",
        {"emoji": THUMBS_UP},
    ),
    (
        "channels:reply_reaction",
        "delete",
        CHANNEL + "messages/1/replies/1/reactions/%F0%9F%91%8D/",
        None,
    ),
]

# Inside a workspace the person can see, but about one channel: a private channel they are not
# in must answer exactly like a channel that doesn't exist.
CHANNEL_ENDPOINTS = [entry for entry in ENDPOINTS if "{channel_id}" in entry[2]]

# Endpoints that are not inside one workspace, so the rule above does not apply.
NOT_WORKSPACE_SCOPED = {"workspaces:list"}
SCOPED_NAMESPACES = ("workspaces:", "channels:")


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
    scoped = {name for name in _names(get_resolver()) if name.startswith(SCOPED_NAMESPACES)}
    assert scoped - NOT_WORKSPACE_SCOPED == {name for name, *_ in ENDPOINTS}


@pytest.fixture
def workspace() -> Workspace:
    owner = make_user(username="owner")
    workspace = Workspace.objects.create(name="Private", slug="private", created_by=owner)
    Member.objects.create(workspace=workspace, user=owner, role=Role.OWNER)
    secret = Channel.objects.create(
        workspace=workspace, name="secret", kind=ChannelKind.PRIVATE, created_by=owner
    )
    ChannelMember.objects.create(channel=secret, user=owner)
    from apps.chat import messages

    first, _ = messages.post(secret, owner, "Only for the secret channel")
    messages.post(secret, owner, "A reply", parent=first)
    return workspace


def _path(template: str, workspace: Workspace, slug: str | None = None) -> str:
    channel = Channel.objects.for_workspace(workspace).get()
    owner = Member.objects.for_workspace(workspace).get(role=Role.OWNER)
    return template.format(
        slug=slug or workspace.slug, user_id=owner.user_id, channel_id=channel.pk
    )


def _call(api: APIClient, method: str, path: str, body: dict[str, Any] | None) -> int:
    response = getattr(api, method)(path, body, format="json")
    return int(response.status_code)


@pytest.mark.parametrize(("name", "method", "path", "body"), ENDPOINTS)
def test_outsider_gets_404(
    api: APIClient, workspace: Workspace, name: str, method: str, path: str, body: Any
) -> None:
    api.force_authenticate(make_user(username="outsider"))

    assert _call(api, method, _path(path, workspace), body) == 404


@pytest.mark.parametrize(("name", "method", "path", "body"), ENDPOINTS)
def test_unknown_workspace_gets_the_same_404(
    api: APIClient, workspace: Workspace, name: str, method: str, path: str, body: Any
) -> None:
    api.force_authenticate(make_user(username="outsider"))

    assert _call(api, method, _path(path, workspace, slug="does-not-exist"), body) == 404


@pytest.mark.parametrize(("name", "method", "path", "body"), ENDPOINTS)
def test_signed_out_gets_403(
    api: APIClient, workspace: Workspace, name: str, method: str, path: str, body: Any
) -> None:
    assert _call(api, method, _path(path, workspace), body) == 403


@pytest.mark.parametrize("role", [Role.ADMIN, Role.MEMBER, Role.GUEST])
@pytest.mark.parametrize(("name", "method", "path", "body"), CHANNEL_ENDPOINTS)
def test_private_channel_is_404_to_workspace_members_outside_it(
    api: APIClient,
    workspace: Workspace,
    role: Role,
    name: str,
    method: str,
    path: str,
    body: Any,
) -> None:
    insider = make_user(username="insider")
    Member.objects.create(workspace=workspace, user=insider, role=role)
    api.force_authenticate(insider)

    assert _call(api, method, _path(path, workspace), body) == 404
    assert not ChannelMember.objects.filter(user=insider).exists()


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


def test_member_cannot_reach_a_channel_in_another_workspace(
    api: APIClient, workspace: Workspace
) -> None:
    mine = Workspace.objects.create(name="Mine", slug="mine")
    me = make_user(username="me")
    Member.objects.create(workspace=mine, user=me, role=Role.OWNER)
    theirs = Channel.objects.for_workspace(workspace).get()
    api.force_authenticate(me)

    response = api.get(f"/api/v1/workspaces/mine/channels/{theirs.pk}/")

    assert response.status_code == 404
