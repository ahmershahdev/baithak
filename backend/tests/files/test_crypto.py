import base64
import io

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from apps.files import crypto

KEY_A = base64.b64encode(b"a" * 32).decode()
KEY_B = base64.b64encode(b"b" * 32).decode()


def sealed(data: bytes) -> bytes:
    return b"".join(crypto.encrypt(io.BytesIO(data)))


def opened(blob: bytes) -> bytes:
    with crypto.decrypt(io.BytesIO(blob)) as stream:
        return stream.read()


@pytest.mark.parametrize(
    "size", [0, 1, crypto.CHUNK - 1, crypto.CHUNK, crypto.CHUNK + 1, 3 * crypto.CHUNK + 7]
)
def test_round_trip(size: int) -> None:
    data = bytes(range(256)) * (size // 256) + bytes(size % 256)

    blob = sealed(data)

    assert opened(blob) == data
    assert data[:64] not in blob or size == 0


def test_the_same_file_encrypts_differently_each_time() -> None:
    first, second = (sealed(b"chai at four") for _ in range(2))

    assert first != second
    assert opened(first) == opened(second)


def test_a_changed_byte_is_caught() -> None:
    blob = bytearray(sealed(b"x" * (crypto.CHUNK + 10)))
    blob[crypto.HEADER + 5] ^= 1

    with pytest.raises(crypto.Tampered):
        opened(bytes(blob))


def test_a_file_cut_at_a_chunk_boundary_is_caught() -> None:
    blob = sealed(b"x" * (2 * crypto.CHUNK + 10))
    first_chunk_only = blob[: crypto.HEADER + crypto.CHUNK + crypto.TAG]

    with pytest.raises(crypto.Tampered):
        opened(first_chunk_only)


def test_a_plain_file_is_not_read_as_encrypted() -> None:
    with pytest.raises(crypto.Tampered):
        opened(b"just some plain text, not ours")


def test_an_old_key_still_opens_files_after_rotation() -> None:
    with override_settings(FILES_ENCRYPTION_KEYS=[KEY_A]):
        blob = sealed(b"before rotation")
    with override_settings(FILES_ENCRYPTION_KEYS=[KEY_B, KEY_A]):
        assert opened(blob) == b"before rotation"
        assert sealed(b"after")[len(crypto.MAGIC) : len(crypto.MAGIC) + 4] == crypto.key_id(
            b"b" * 32
        )
    with override_settings(FILES_ENCRYPTION_KEYS=[KEY_B]), pytest.raises(crypto.Tampered):
        opened(blob)


@pytest.mark.parametrize(
    ("keys", "message"),
    [
        ([], "Set FILES_ENCRYPTION_KEYS"),
        (["not base64!"], "isn't base64"),
        ([KEY_A[:20]], "32 bytes"),
    ],
)
def test_bad_keys_stop_encryption(keys: list[str], message: str) -> None:
    with (
        override_settings(FILES_ENCRYPTION_KEYS=keys),
        pytest.raises(ImproperlyConfigured, match=message),
    ):
        sealed(b"anything")
