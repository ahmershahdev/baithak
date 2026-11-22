from apps.core.webhooks import MAX_ATTEMPTS, digest, gives_up, new_token, retry_delay


def test_tokens_are_long_and_different() -> None:
    first, second = new_token(), new_token()

    assert first != second
    assert len(first) >= 40


def test_the_digest_is_sha256_in_hex() -> None:
    # The SHA-256 test vector for "abc" (FIPS 180-2).
    assert digest("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_retries_back_off_up_to_an_hour() -> None:
    assert [retry_delay(n) for n in (1, 2, 3, 4, 5)] == [30, 60, 120, 240, 480]
    assert retry_delay(20) == 3600


def test_it_gives_up_after_the_last_attempt() -> None:
    assert not gives_up(MAX_ATTEMPTS - 1)
    assert gives_up(MAX_ATTEMPTS)
