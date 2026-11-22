import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat.models import Channel, ChannelMember, Message, Reaction
from apps.core.roles import Role
from apps.files.models import Attachment
from apps.workspaces.models import AuditEvent, Member, Workspace
from tests.accounts.factories import PASSWORD, make_user

pytestmark = pytest.mark.django_db

DELETE = "/api/v1/auth/delete-account/"
THUMBS_UP = "\U0001f44d"


@pytest.fixture(autouse=True)
def _clean_files() -> Iterator[None]:
    yield
    shutil.rmtree(settings.FILES_ROOT, ignore_errors=True)


@pytest.fixture
def amna(api: APIClient) -> User:
    user = make_user(username="amna")
    api.force_authenticate(user)
    return user


def new_workspace(api: APIClient, name: str) -> Workspace:
    response = api.post("/api/v1/workspaces/", {"name": name}, format="json")
    return Workspace.objects.get(slug=response.json()["slug"])


def general(workspace: Workspace) -> Channel:
    return Channel.objects.for_workspace(workspace).get(name="general")


def join(workspace: Workspace, user: User, role: Role) -> None:
    Member.objects.create(workspace=workspace, user=user, role=role)
    ChannelMember.objects.create(channel=general(workspace), user=user)


def post(api: APIClient, channel: Channel, body: str) -> Message:
    url = f"/api/v1/workspaces/{channel.workspace.slug}/channels/{channel.pk}/messages/"
    response = api.post(url, {"body": body}, format="json")
    return Message.objects.get(pk=response.json()["id"])


def upload(api: APIClient, channel: Channel) -> Attachment:
    url = f"/api/v1/workspaces/{channel.workspace.slug}/channels/{channel.pk}/files/"
    file = SimpleUploadedFile("notes.txt", b"chai at four\n", content_type="text/plain")
    response = api.post(url, {"file": file}, format="multipart")
    return Attachment.objects.get(pk=response.json()["id"])


def on_disk(attachment: Attachment) -> bool:
    return (Path(settings.FILES_ROOT) / attachment.storage_key).exists()


def delete(api: APIClient, password: str = PASSWORD) -> tuple[int, dict[str, object]]:
    with TestCase.captureOnCommitCallbacks(execute=True):
        response = api.post(DELETE, {"password": password}, format="json")
    return response.status_code, response.json() if response.content else {}


def test_needs_sign_in(api: APIClient) -> None:
    assert api.post(DELETE, {"password": PASSWORD}, format="json").status_code == 403


def test_wrong_password_keeps_the_account(api: APIClient, amna: User) -> None:
    status, body = delete(api, "Not-My-Password-1")

    assert status == 400
    assert body["detail"] == "The password is wrong."
    assert User.objects.filter(pk=amna.pk).exists()


def test_last_owner_of_a_shared_workspace_must_hand_it_over(api: APIClient, amna: User) -> None:
    workspace = new_workspace(api, "Chai and Code")
    join(workspace, make_user(username="bilal"), Role.ADMIN)

    status, body = delete(api)

    assert status == 409
    assert body["workspaces"] == [{"slug": workspace.slug, "name": "Chai and Code"}]
    assert User.objects.filter(pk=amna.pk).exists()
    assert Member.objects.filter(workspace=workspace, user=amna).exists()


def test_leaves_shared_workspaces_and_keeps_posts_without_an_author(
    api: APIClient, amna: User
) -> None:
    bilal = make_user(username="bilal")
    api.force_authenticate(bilal)
    workspace = new_workspace(api, "Monsoon Press")
    join(workspace, amna, Role.MEMBER)
    api.force_authenticate(amna)
    message = post(api, general(workspace), "Proofs are on the desk.")
    Reaction.objects.create(message=message, user=amna, emoji=THUMBS_UP)
    left_behind = upload(api, general(workspace))

    status, _ = delete(api)

    assert status == 204
    assert not User.objects.filter(pk=amna.pk).exists()
    message.refresh_from_db()
    assert message.body == "Proofs are on the desk."
    assert message.author is None
    assert not Reaction.objects.filter(message=message).exists()
    assert not Member.objects.filter(workspace=workspace, user_id=amna.pk).exists()
    assert not Attachment.objects.filter(pk=left_behind.pk).exists()
    assert not on_disk(left_behind)
    event = AuditEvent.objects.for_workspace(workspace).get(action="member.remove")
    assert event.changes == {"user": "amna", "reason": "account deleted"}


def test_workspaces_with_nobody_else_go_with_the_account(api: APIClient, amna: User) -> None:
    workspace = new_workspace(api, "Just Me")
    message = post(api, general(workspace), "A note to self.")
    attachment = upload(api, general(workspace))
    url = f"/api/v1/workspaces/{workspace.slug}/channels/{general(workspace).pk}/messages/"
    api.post(url, {"body": "With a file.", "attachments": [attachment.pk]}, format="json")

    status, _ = delete(api)

    assert status == 204
    assert not Workspace.objects.filter(pk=workspace.pk).exists()
    assert not Message.objects.filter(pk=message.pk).exists()
    assert not on_disk(attachment)


def test_an_owner_with_another_owner_can_leave(api: APIClient, amna: User) -> None:
    workspace = new_workspace(api, "Two Owners")
    join(workspace, make_user(username="bilal"), Role.OWNER)

    status, _ = delete(api)

    assert status == 204
    assert Workspace.objects.filter(pk=workspace.pk).exists()


def test_signs_out_and_frees_the_email(amna: User) -> None:
    client = APIClient()
    client.login(email="amna@example.com", password=PASSWORD)

    status, _ = delete(client)

    assert status == 204
    assert client.get("/api/v1/auth/me/").status_code == 204
    assert not User.objects.filter(email="amna@example.com").exists()
