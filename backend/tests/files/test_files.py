import io
import shutil
from collections.abc import Iterator
from typing import Any

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember, Message
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.files import links
from apps.files.models import Attachment
from apps.files.tasks import MAX_PIXELS, PREVIEW_SIDE, make_preview
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/workspaces/karachi-team/channels/"


@pytest.fixture(autouse=True)
def _clean_files() -> Iterator[None]:
    yield
    shutil.rmtree(settings.FILES_ROOT, ignore_errors=True)


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


def png(width: int = 1600, height: int = 900) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), (199, 58, 30)).save(out, "PNG")
    return out.getvalue()


def upload(api: APIClient, channel: Channel, name: str, data: bytes, kind: str = "") -> Any:
    """Commit callbacks run, so an image's preview is made (Celery is eager in tests)."""
    file = SimpleUploadedFile(name, data, content_type=kind or "application/octet-stream")
    with TestCase.captureOnCommitCallbacks(execute=True):
        return api.post(f"{BASE}{channel.pk}/files/", {"file": file}, format="multipart")


def send(api: APIClient, channel: Channel, body: str, attachments: list[int]) -> Any:
    payload = {"body": body, "attachments": attachments}
    return api.post(f"{BASE}{channel.pk}/messages/", payload, format="json")


def download(api: APIClient, url: str) -> Any:
    response: Any = api.get(url)
    if response.status_code == 200:
        response.body = b"".join(response.streaming_content)
    return response


class TestUploading:
    def test_an_image_is_stored_with_its_sniffed_type_and_a_preview(
        self, api: APIClient, general: Channel
    ) -> None:
        response = upload(api, general, "../../beach.png", png(), "text/html")

        assert response.status_code == 201
        body = response.json()
        assert (body["name"], body["content_type"]) == ("beach.png", "image/png")
        attachment = Attachment.objects.get(pk=body["id"])
        assert attachment.preview_key
        assert (attachment.width, attachment.height) == (1600, 900)
        assert str(settings.FILES_ROOT) not in body["url"]

    def test_text_claiming_to_be_an_image_is_kept_as_text(
        self, api: APIClient, general: Channel
    ) -> None:
        response = upload(api, general, "x.png", b"<script>alert(1)</script>", "image/png")

        assert response.json()["content_type"] == "text/plain"
        assert response.json()["preview_url"] is None

    @pytest.mark.parametrize("data", [b"MZ\x90\x00 windows program", b"", b"\x7fELF\x02\x01\x01"])
    def test_other_files_are_refused(self, api: APIClient, general: Channel, data: bytes) -> None:
        assert upload(api, general, "tool.exe", data).status_code == 400

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=None)
    def test_a_file_over_the_limit_is_refused(
        self, api: APIClient, general: Channel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("apps.core.files.MAX_SIZE", 10)

        assert upload(api, general, "notes.txt", b"more than ten bytes").status_code == 400

    def test_someone_outside_the_channel_cannot_upload(
        self, api: APIClient, workspace: Workspace, owner: User
    ) -> None:
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE, created_by=owner
        )
        reader = make_user(username="reader")
        Member.objects.create(workspace=workspace, user=reader, role=Role.MEMBER)
        ChannelMember.objects.create(channel=secret, user=owner)
        api.force_authenticate(reader)

        assert upload(api, secret, "a.txt", b"hello").status_code == 404

    def test_an_image_bomb_gets_no_preview(self, api: APIClient, general: Channel) -> None:
        side = int(MAX_PIXELS**0.5) + 100
        out = io.BytesIO()
        Image.new("1", (side, side)).save(out, "PNG")

        response = upload(api, general, "bomb.png", out.getvalue())

        assert response.status_code == 201
        assert Attachment.objects.get(pk=response.json()["id"]).preview_key == ""


class TestSending:
    def test_a_message_carries_its_files(self, api: APIClient, general: Channel) -> None:
        file_id = upload(api, general, "notes.txt", b"chai at four").json()["id"]

        response = send(api, general, "", [file_id])

        assert response.status_code == 201
        assert [a["name"] for a in response.json()["attachments"]] == ["notes.txt"]
        history = api.get(f"{BASE}{general.pk}/messages/").json()["messages"]
        assert history[0]["attachments"][0]["id"] == file_id

    def test_an_empty_message_without_files_is_refused(
        self, api: APIClient, general: Channel
    ) -> None:
        assert send(api, general, "  ", []).status_code == 400

    def test_a_file_can_be_sent_once(self, api: APIClient, general: Channel) -> None:
        file_id = upload(api, general, "notes.txt", b"chai").json()["id"]
        send(api, general, "first", [file_id])

        again = send(api, general, "second", [file_id])

        assert again.status_code == 400
        assert Message.objects.filter(channel=general).count() == 1

    def test_someone_elses_file_cannot_be_sent(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        file_id = upload(api, general, "notes.txt", b"mine").json()["id"]
        bilal = make_user(username="bilal")
        Member.objects.create(workspace=workspace, user=bilal, role=Role.MEMBER)
        ChannelMember.objects.create(channel=general, user=bilal)
        api.force_authenticate(bilal)

        assert send(api, general, "look", [file_id]).status_code == 400

    def test_a_preview_made_after_sending_reaches_the_message(
        self, api: APIClient, owner: User, general: Channel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("apps.files.views.make_preview.delay", lambda _id: None)
        file_id = upload(api, general, "beach.png", png()).json()["id"]
        sent = send(api, general, "", [file_id]).json()
        assert sent["attachments"][0]["preview_url"] is None

        make_preview(file_id)

        page = api.get(f"{BASE}{general.pk}/messages/", {"after_event": sent["event"]}).json()
        attached = page["messages"][0]["attachments"][0]
        assert attached["preview_url"] is not None
        assert (attached["width"], attached["height"]) == (1600, 900)

    def test_deleting_the_message_deletes_its_files(
        self, api: APIClient, owner: User, general: Channel
    ) -> None:
        file_id = upload(api, general, "beach.png", png()).json()["id"]
        attachment = Attachment.objects.get(pk=file_id)
        stored = settings.FILES_ROOT / attachment.storage_key
        message = Message.objects.get(pk=send(api, general, "", [file_id]).json()["id"])

        with TestCase.captureOnCommitCallbacks(execute=True):
            messages.delete(message)

        assert not Attachment.objects.filter(pk=file_id).exists()
        assert not stored.exists()


class TestDownloading:
    def test_the_signed_link_serves_the_file_safely(self, api: APIClient, general: Channel) -> None:
        body = upload(api, general, "notes.txt", b"chai at four").json()
        send(api, general, "", [body["id"]])

        response = download(api, body["url"])

        assert response.status_code == 200
        assert response.body == b"chai at four"
        assert response["Content-Type"].startswith("text/plain")
        assert response["X-Content-Type-Options"] == "nosniff"
        assert "sandbox" in response["Content-Security-Policy"]
        assert response["Content-Disposition"].startswith("attachment")

    def test_images_open_in_the_browser_and_have_a_preview(
        self, api: APIClient, general: Channel
    ) -> None:
        body = upload(api, general, "beach.png", png()).json()

        original = download(api, body["url"])
        # The upload answers before its preview exists; the message carries it later.
        preview = download(api, links.url("karachi-team", body["id"], links.PREVIEW))

        assert original["Content-Disposition"].startswith("inline")
        assert preview["Content-Type"] == "image/webp"
        with Image.open(io.BytesIO(preview.body)) as image:
            assert max(image.size) == PREVIEW_SIDE

    def test_a_forged_or_expired_link_is_404(
        self, api: APIClient, general: Channel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        body = upload(api, general, "notes.txt", b"chai").json()

        assert download(api, body["url"][:-3] + "abc/").status_code == 404
        monkeypatch.setattr(settings, "FILE_LINK_MAX_AGE", -1)
        assert download(api, body["url"]).status_code == 404

    def test_a_file_not_yet_sent_is_only_its_uploaders(
        self, api: APIClient, workspace: Workspace, general: Channel
    ) -> None:
        url = upload(api, general, "draft.txt", b"not sent").json()["url"]
        bilal = make_user(username="bilal")
        Member.objects.create(workspace=workspace, user=bilal, role=Role.MEMBER)
        api.force_authenticate(bilal)

        assert download(api, url).status_code == 404

    def test_leaving_a_private_channel_takes_its_files_away(
        self, api: APIClient, owner: User, workspace: Workspace
    ) -> None:
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE, created_by=owner
        )
        ChannelMember.objects.create(channel=secret, user=owner)
        bilal = make_user(username="bilal")
        Member.objects.create(workspace=workspace, user=bilal, role=Role.MEMBER)
        ChannelMember.objects.create(channel=secret, user=bilal)
        file_id = upload(api, secret, "plan.txt", b"secret plan").json()["id"]
        send(api, secret, "", [file_id])
        url = links.url("karachi-team", file_id, links.ORIGINAL)
        ChannelMember.objects.filter(channel=secret, user=bilal).delete()
        api.force_authenticate(bilal)

        assert download(api, url).status_code == 404

    def test_a_link_from_another_workspace_is_404(
        self, api: APIClient, owner: User, general: Channel
    ) -> None:
        file_id = upload(api, general, "notes.txt", b"chai").json()["id"]
        send(api, general, "", [file_id])
        api.post("/api/v1/workspaces/", {"name": "Other Team"}, format="json")

        url = links.url("other-team", file_id, links.ORIGINAL)

        assert download(api, url).status_code == 404
