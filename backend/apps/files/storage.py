"""Files on disk under FILES_ROOT, outside anything the web server serves. They are only
ever read back through the signed download view. New files are encrypted (apps/files/crypto.py);
files from before encryption stay plain until `manage.py encrypt_files` converts them."""

import io
import os
import uuid
from typing import IO

from django.conf import settings
from django.core.files.storage import FileSystemStorage

from apps.files import crypto


def _storage() -> FileSystemStorage:
    # No base_url: nothing here has a public address.
    return FileSystemStorage(location=settings.FILES_ROOT)


def new_key() -> str:
    name = uuid.uuid4().hex
    return f"{name[:2]}/{name}"


def save(content: IO[bytes]) -> str:
    """Encrypts and stores a file; returns its key."""
    key = new_key()
    path = _storage().path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # "x": keys are random, so an existing file means something is wrong; never overwrite it.
    with open(path, "xb") as out:
        for piece in crypto.encrypt(content):
            out.write(piece)
    return key


def save_bytes(data: bytes) -> str:
    return save(io.BytesIO(data))


def open_file(key: str, *, encrypted: bool = True) -> IO[bytes]:
    raw = _storage().open(key, "rb")
    return crypto.decrypt(raw) if encrypted else raw


def read_all(key: str, *, encrypted: bool = True) -> bytes:
    with open_file(key, encrypted=encrypted) as stream:
        return stream.read()


def delete(key: str) -> None:
    if key:
        _storage().delete(key)
