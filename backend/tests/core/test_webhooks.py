from apps.core.webhooks import digest, new_token


def test_tokens_are_long_and_different() -> None:
    first, second = new_token(), new_token()

    assert first != second
    assert len(first) >= 40


def test_the_digest_is_sha256_in_hex() -> None:
    # The SHA-256 test vector for "abc" (FIPS 180-2).
    assert digest("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
