import io
import os
import shutil
import socket
import socketserver
import threading
import zipfile
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat.models import Channel, Message
from apps.files import links, scanning, storage, tasks
from apps.files.models import Attachment, Scan
from apps.workspaces.models import Workspace
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


def upload(api: APIClient, channel: Channel, name: str, data: bytes) -> Any:
    file = SimpleUploadedFile(name, data, content_type="application/octet-stream")
    with TestCase.captureOnCommitCallbacks(execute=True):
        return api.post(f"{BASE}{channel.pk}/files/", {"file": file}, format="multipart")


def uploaded(api: APIClient, channel: Channel, name: str, data: bytes) -> Attachment:
    response = upload(api, channel, name, data)
    assert response.status_code == 201, response.json()
    return Attachment.objects.get(pk=response.json()["id"])


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (40, 30), (199, 58, 30)).save(out, "PNG")
    return out.getvalue()


class TestScanningUploads:
    def test_a_clean_file_is_stored_encrypted(self, api: APIClient, general: Channel) -> None:
        attachment = uploaded(api, general, "notes.txt", b"chai at four, every day")

        assert attachment.scan == Scan.CLEAN
        assert attachment.encrypted
        on_disk = (settings.FILES_ROOT / attachment.storage_key).read_bytes()
        assert b"chai at four" not in on_disk
        assert storage.read_all(attachment.storage_key) == b"chai at four, every day"

    def test_a_virus_is_refused_and_its_bytes_deleted(
        self, api: APIClient, general: Channel
    ) -> None:
        attachment = uploaded(api, general, "eicar.txt", scanning.EICAR)

        assert attachment.scan == Scan.INFECTED
        assert attachment.scan_detail == "Eicar-Test-Signature"
        assert not (settings.FILES_ROOT / attachment.storage_key).exists()
        url = links.url("karachi-team", attachment.pk, links.ORIGINAL)
        assert api.get(url).status_code == 404
        refused = api.post(
            f"{BASE}{general.pk}/messages/",
            {"body": "", "attachments": [attachment.pk]},
            format="json",
        )
        assert refused.status_code == 400

    @pytest.mark.parametrize(
        ("name", "data", "reason"),
        [
            ("cut.png", png()[:-30], "damaged"),
            ("script.pdf", b"%PDF-1.7\n<< /S /JavaScript >>\n%%EOF\n", "run scripts"),
            ("broken.zip", b"PK\x03\x04 not really a zip", "damaged"),
            # Valid in the first 4 KB the upload sniffs, broken after it.
            ("latin1.txt", b"chai " * 1000 + b"\xe9\xe9", "UTF-8"),
        ],
    )
    def test_damaged_or_risky_files_are_refused(
        self, api: APIClient, general: Channel, name: str, data: bytes, reason: str | None
    ) -> None:
        attachment = uploaded(api, general, name, data)

        assert attachment.scan == Scan.DAMAGED
        assert reason is None or reason in attachment.scan_detail

    def test_office_macros_are_refused(self, api: APIClient, general: Channel) -> None:
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("word/document.xml", "<w:document/>")
            archive.writestr("word/vbaProject.bin", b"macro")

        attachment = uploaded(api, general, "report.docm", out.getvalue())

        assert attachment.scan == Scan.DAMAGED
        assert "macros" in attachment.scan_detail

    def test_a_file_being_checked_can_be_sent_and_its_link_comes_later(
        self, api: APIClient, general: Channel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("apps.files.views.scan_file.delay", lambda _id: None)
        attachment = uploaded(api, general, "notes.txt", b"chai at four")
        sent = api.post(
            f"{BASE}{general.pk}/messages/",
            {"body": "", "attachments": [attachment.pk]},
            format="json",
        ).json()
        assert sent["attachments"][0]["url"] is None
        assert api.get(links.url("karachi-team", attachment.pk, links.ORIGINAL)).status_code == 404

        tasks.scan_file(attachment.pk)

        page = api.get(f"{BASE}{general.pk}/messages/", {"after_event": sent["event"]}).json()
        shown = page["messages"][0]["attachments"][0]
        assert shown["scan"] == "clean"
        assert shown["url"] is not None

    def test_a_refused_file_in_a_message_says_why(
        self, api: APIClient, general: Channel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("apps.files.views.scan_file.delay", lambda _id: None)
        attachment = uploaded(api, general, "eicar.txt", scanning.EICAR)
        sent = api.post(
            f"{BASE}{general.pk}/messages/",
            {"body": "", "attachments": [attachment.pk]},
            format="json",
        ).json()

        tasks.scan_file(attachment.pk)

        shown = Message.objects.get(pk=sent["id"]).attachments.get()
        assert shown.scan == Scan.INFECTED
        page = api.get(f"{BASE}{general.pk}/messages/", {"after_event": sent["event"]}).json()
        assert (
            page["messages"][0]["attachments"][0]["scan_note"]
            == "Removed: a virus scan flagged it."
        )


class TestWhenTheScannerIsDown:
    def test_the_file_stays_pending_and_the_scan_is_retried(
        self, api: APIClient, general: Channel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("apps.files.views.scan_file.delay", lambda _id: None)
        attachment = uploaded(api, general, "notes.txt", b"chai")

        def down(_data: bytes) -> scanning.Verdict:
            raise scanning.ScanUnavailable("Connection refused")

        monkeypatch.setattr(scanning, "scan", down)
        # Called directly (not by a worker), Celery's retry raises the original error.
        with pytest.raises(scanning.ScanUnavailable):
            tasks.scan_file(attachment.pk)

        attachment.refresh_from_db()
        assert attachment.scan == Scan.PENDING

    def test_stuck_files_are_queued_again(
        self, api: APIClient, general: Channel, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("apps.files.views.scan_file.delay", lambda _id: None)
        old = uploaded(api, general, "old.txt", b"chai")
        new = uploaded(api, general, "new.txt", b"chai")
        Attachment.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - tasks.STUCK_AFTER - timedelta(minutes=1)
        )
        queued: list[int] = []
        monkeypatch.setattr(tasks.scan_file, "delay", queued.append)

        tasks.rescan_stuck()

        assert queued == [old.pk]
        assert new.pk not in queued

    def test_a_second_scan_of_the_same_file_changes_nothing(
        self, api: APIClient, general: Channel
    ) -> None:
        attachment = uploaded(api, general, "notes.txt", b"chai")

        tasks._finish(attachment.pk, Scan.INFECTED, "late verdict")

        attachment.refresh_from_db()
        assert attachment.scan == Scan.CLEAN


class FakeClamd(socketserver.BaseRequestHandler):
    reply = b"stream: OK\0"
    received: bytes = b""

    def handle(self) -> None:
        data = b""
        while not data.endswith(b"\0\0\0\0") or len(data) < 14:
            chunk = self.request.recv(65536)
            if not chunk:
                break
            data += chunk
        FakeClamd.received = data
        self.request.sendall(FakeClamd.reply)


@pytest.fixture
def clamd() -> Iterator[tuple[str, int]]:
    server = socketserver.TCPServer(("127.0.0.1", 0), FakeClamd)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    yield str(host), int(port)
    server.shutdown()
    server.server_close()


class TestTheClamdClient:
    def test_it_streams_the_file_in_framed_chunks(self, clamd: tuple[str, int]) -> None:
        FakeClamd.reply = b"stream: OK\0"
        data = b"x" * (scanning.SEND + 5)
        with override_settings(FILE_SCANNER="clamd", CLAMAV_HOST=clamd[0], CLAMAV_PORT=clamd[1]):
            verdict = scanning.scan(data)

        assert verdict.clean
        sent = FakeClamd.received
        assert sent.startswith(b"zINSTREAM\0")
        framed = sent[len(b"zINSTREAM\0") :]
        assert framed[:4] == scanning.SEND.to_bytes(4, "big")
        assert framed.endswith((5).to_bytes(4, "big") + b"xxxxx" + b"\0\0\0\0")

    def test_a_signature_is_a_refusal(self, clamd: tuple[str, int]) -> None:
        FakeClamd.reply = b"stream: Win.Test.EICAR_HDB-1 FOUND\0"
        with override_settings(FILE_SCANNER="clamd", CLAMAV_HOST=clamd[0], CLAMAV_PORT=clamd[1]):
            verdict = scanning.scan(b"anything")

        assert (verdict.clean, verdict.detail) == (False, "Win.Test.EICAR_HDB-1")

    def test_an_error_reply_means_try_later(self, clamd: tuple[str, int]) -> None:
        FakeClamd.reply = b"INSTREAM size limit exceeded. ERROR\0"
        with (
            override_settings(FILE_SCANNER="clamd", CLAMAV_HOST=clamd[0], CLAMAV_PORT=clamd[1]),
            pytest.raises(scanning.ScanUnavailable),
        ):
            scanning.scan(b"anything")

    def test_no_clamd_means_try_later(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        with (
            override_settings(FILE_SCANNER="clamd", CLAMAV_HOST="127.0.0.1", CLAMAV_PORT=port),
            pytest.raises(scanning.ScanUnavailable),
        ):
            scanning.scan(b"anything")


@pytest.mark.skipif(not os.environ.get("CLAMAV_INTEGRATION"), reason="needs a running clamd")
def test_the_real_clamd_flags_eicar() -> None:
    host = os.environ.get("CLAMAV_HOST", "clamav")
    with override_settings(FILE_SCANNER="clamd", CLAMAV_HOST=host):
        assert scanning.scan(b"just chai").clean
        assert not scanning.scan(scanning.EICAR).clean


class TestEncryptingOldFiles:
    def test_plain_files_from_before_are_encrypted_in_place(
        self, api: APIClient, general: Channel, owner: User
    ) -> None:
        key = storage.new_key()
        path = settings.FILES_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"an old plain file")
        attachment = Attachment.objects.create(
            workspace=general.workspace,
            channel=general,
            uploader=owner,
            name="old.txt",
            content_type="text/plain",
            size=17,
            storage_key=key,
            encrypted=False,
            scan=Scan.CLEAN,
        )

        with TestCase.captureOnCommitCallbacks(execute=True):
            call_command("encrypt_files", stdout=io.StringIO())

        attachment.refresh_from_db()
        assert attachment.encrypted
        assert attachment.storage_key != key
        assert not path.exists()
        assert storage.read_all(attachment.storage_key) == b"an old plain file"
