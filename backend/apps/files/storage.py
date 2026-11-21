"""Files on disk under FILES_ROOT, outside anything the web server serves. They are only
ever read back through the signed download view."""

import uuid
from typing import IO

from django.conf import settings
from django.core.files.base import ContentFile, File
from django.core.files.storage import FileSystemStorage


def _storage() -> FileSystemStorage:
    # No base_url: nothing here has a public address.
    return FileSystemStorage(location=settings.FILES_ROOT)


def new_key() -> str:
    name = uuid.uuid4().hex
    return f"{name[:2]}/{name}"


def save(content: IO[bytes]) -> str:
    return _storage().save(new_key(), File(content))


def save_bytes(data: bytes) -> str:
    return _storage().save(new_key(), ContentFile(data))


def open_file(key: str) -> IO[bytes]:
    return _storage().open(key, "rb")


def delete(key: str) -> None:
    if key:
        _storage().delete(key)
