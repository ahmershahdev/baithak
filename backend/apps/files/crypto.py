"""Files at rest are AES-256-GCM in 64 KiB chunks, so they can be streamed without holding a
whole file in memory.

Layout: MAGIC, a 4-byte key id, an 8-byte random nonce prefix, then the sealed chunks. Chunk n
uses the nonce prefix + n (4 bytes, big-endian), and its associated data is the header plus one
byte that is 1 only on the last chunk. A file cut short, reordered or spliced from another file
fails to open instead of reading as a shorter file.
"""

import base64
import binascii
import hashlib
import io
import os
from collections.abc import Iterator
from typing import IO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

MAGIC = b"BKF1"
CHUNK = 64 * 1024
TAG = 16
PREFIX = 8
HEADER = len(MAGIC) + 4 + PREFIX
LAST, MORE = b"\x01", b"\x00"


class Tampered(Exception):
    """The stored bytes are not what was written: wrong key, cut short or changed."""


def _keys() -> list[bytes]:
    keys = []
    for value in settings.ENCRYPTION_KEYS:
        try:
            key = base64.b64decode(value, validate=True)
        except binascii.Error as error:
            raise ImproperlyConfigured("ENCRYPTION_KEYS holds a key that isn't base64.") from error
        if len(key) != 32:
            raise ImproperlyConfigured("Each key in ENCRYPTION_KEYS must be 32 bytes.")
        keys.append(key)
    if not keys:
        raise ImproperlyConfigured("Set ENCRYPTION_KEYS to encrypt stored files and secrets.")
    return keys


def key_id(key: bytes) -> bytes:
    return hashlib.sha256(key).digest()[:4]


def _nonce(prefix: bytes, counter: int) -> bytes:
    if counter >= 2**32:
        raise ValueError("File too large to encrypt.")
    return prefix + counter.to_bytes(4, "big")


def encrypt(source: IO[bytes]) -> Iterator[bytes]:
    key = _keys()[0]
    prefix = os.urandom(PREFIX)
    header = MAGIC + key_id(key) + prefix
    aead = AESGCM(key)
    yield header
    counter = 0
    chunk = source.read(CHUNK)
    while True:
        following = source.read(CHUNK)
        last = not following
        aad = header + (LAST if last else MORE)
        yield aead.encrypt(_nonce(prefix, counter), chunk, aad)
        if last:
            return
        chunk, counter = following, counter + 1


class _Decrypting(io.RawIOBase):
    def __init__(self, raw: IO[bytes]) -> None:
        self._raw = raw
        header = raw.read(HEADER)
        if len(header) != HEADER or not header.startswith(MAGIC):
            raise Tampered("Not an encrypted Baithak file.")
        wanted = header[len(MAGIC) : len(MAGIC) + 4]
        key = next((k for k in _keys() if key_id(k) == wanted), None)
        if key is None:
            raise Tampered("No key in ENCRYPTION_KEYS opens this file.")
        self._aead = AESGCM(key)
        self._header = header
        self._prefix = header[-PREFIX:]
        self._counter = 0
        self._plain = memoryview(b"")
        self._done = False
        self._next = raw.read(CHUNK + TAG)

    def readable(self) -> bool:
        return True

    def _fill(self) -> None:
        sealed = self._next
        following = self._raw.read(CHUNK + TAG)
        last = not following
        aad = self._header + (LAST if last else MORE)
        try:
            plain = self._aead.decrypt(_nonce(self._prefix, self._counter), sealed, aad)
        except (InvalidTag, ValueError) as error:
            raise Tampered("A chunk failed its check.") from error
        self._plain = memoryview(plain)
        self._counter += 1
        self._next = following
        self._done = last

    def readinto(self, buffer: bytearray | memoryview) -> int:  # type: ignore[override]
        while not self._plain and not self._done:
            self._fill()
        size = min(len(buffer), len(self._plain))
        buffer[:size] = self._plain[:size]
        self._plain = self._plain[size:]
        return size

    def close(self) -> None:
        self._raw.close()
        super().close()


def decrypt(raw: IO[bytes]) -> IO[bytes]:
    """A readable stream of the plain bytes. Reading raises Tampered if a check fails."""
    return io.BufferedReader(_Decrypting(raw), buffer_size=CHUNK)


SEALED = b"BKS1"


def seal(secret: bytes) -> bytes:
    """A small secret (such as a two-step sign-in key) encrypted in one piece."""
    key = _keys()[0]
    nonce = os.urandom(12)
    header = SEALED + key_id(key)
    return header + nonce + AESGCM(key).encrypt(nonce, secret, header)


def unseal(blob: bytes) -> bytes:
    header, nonce, sealed = blob[:8], blob[8:20], blob[20:]
    key = next((k for k in _keys() if key_id(k) == header[4:]), None)
    if not header.startswith(SEALED) or key is None:
        raise Tampered("No key in ENCRYPTION_KEYS opens this secret.")
    try:
        return AESGCM(key).decrypt(nonce, sealed, header)
    except InvalidTag as error:
        raise Tampered("The secret failed its check.") from error
