from apps.core.webhooks import digest, new_token


def test_tokens_are_long_and_different() -> None:
    first, second = new_token(), new_token()

    assert first != second
    assert len(first) >= 40


def test_the_digest_is_stable_and_not_the_token() -> None:
    token = new_token()

    assert digest(token) == digest(token)
    assert digest(token) != token
    assert len(digest(token)) == 64
