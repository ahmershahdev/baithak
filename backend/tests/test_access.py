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
from apps.integrations.models import Webhook
from apps.issues.models import Label, Project
from apps.issues.services import create_issue
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

MEMBER = "/api/v1/workspaces/{slug}/members/{user_id}/"
CHANNEL = "/api/v1/workspaces/{slug}/channels/{channel_id}/"
PROJECT = "/api/v1/workspaces/{slug}/projects/SEC/"
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
    ("channels:files", "post", CHANNEL + "files/", None),
    ("projects:list", "get", "/api/v1/workspaces/{slug}/projects/", None),
    ("projects:list", "post", "/api/v1/workspaces/{slug}/projects/", {"key": "NEW", "name": "N"}),
    ("projects:detail", "get", PROJECT, None),
    ("projects:detail", "patch", PROJECT, {"name": "Taken over"}),
    ("projects:labels", "get", PROJECT + "labels/", None),
    ("projects:labels", "post", PROJECT + "labels/", {"name": "x", "color": "danger"}),
    ("projects:label", "patch", PROJECT + "labels/{label_id}/", {"name": "y"}),
    ("projects:label", "delete", PROJECT + "labels/{label_id}/", None),
    ("projects:issues", "get", PROJECT + "issues/", None),
    ("projects:issues", "post", PROJECT + "issues/", {"title": "Let me in"}),
    ("projects:issue", "get", PROJECT + "issues/1/", None),
    ("projects:issue", "patch", PROJECT + "issues/1/", {"title": "Changed"}),
    ("projects:issue-history", "get", PROJECT + "issues/1/history/", None),
    ("notifications:list", "get", "/api/v1/workspaces/{slug}/notifications/", None),
    ("notifications:read", "post", "/api/v1/workspaces/{slug}/notifications/read/", {"all": True}),
    ("search:messages", "get", "/api/v1/workspaces/{slug}/search/messages/?q=secret", None),
    ("search:files", "get", "/api/v1/workspaces/{slug}/search/files/?q=secret", None),
    ("search:issues", "get", "/api/v1/workspaces/{slug}/search/issues/?q=secret", None),
    ("integrations:webhooks", "get", "/api/v1/workspaces/{slug}/integrations/webhooks/", None),
    (
        "integrations:webhooks",
        "post",
        "/api/v1/workspaces/{slug}/integrations/webhooks/",
        {"kind": "github", "channel_id": 1, "repo": "team/app"},
    ),
    (
        "integrations:webhook",
        "delete",
        "/api/v1/workspaces/{slug}/integrations/webhooks/{webhook_id}/",
        None,
    ),
    ("files:download", "get", "/api/v1/workspaces/{slug}/files/not-a-real-token/", None),
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
SCOPED_NAMESPACES = (
    "workspaces:",
    "channels:",
    "files:",
    "search:",
    "notifications:",
    "projects:",
    "integrations:",
)


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
    project = Project.objects.create(workspace=workspace, key="SEC", name="Secret")
    Label.objects.create(workspace=workspace, project=project, name="bug", color="danger")
    create_issue(project, owner, {"title": "Only for members"})
    Webhook.objects.create(
        workspace=workspace, channel=secret, kind="github", repo="team/app", token="t", secret="s"
    )
    return workspace


def _path(template: str, workspace: Workspace, slug: str | None = None) -> str:
    channel = Channel.objects.for_workspace(workspace).get()
    owner = Member.objects.for_workspace(workspace).get(role=Role.OWNER)
    label = Label.objects.for_workspace(workspace).get()
    return template.format(
        slug=slug or workspace.slug,
        user_id=owner.user_id,
        channel_id=channel.pk,
        label_id=label.pk,
        webhook_id=Webhook.objects.for_workspace(workspace).get().pk,
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
