import hashlib
import hmac
from typing import Any

import pytest

from apps.core.github import describe, repository, signature_ok, valid_repo


def pull(action: str, **extra: Any) -> dict[str, Any]:
    return {
        "action": action,
        "sender": {"login": "amna"},
        "repository": {"full_name": "team/app"},
        "pull_request": {
            "number": 12,
            "title": "Fix uploads",
            "html_url": "https://github.com/team/app/pull/12",
            **extra,
        },
    }


def issue(action: str) -> dict[str, Any]:
    return {
        "action": action,
        "sender": {"login": "bilal"},
        "repository": {"full_name": "team/app"},
        "issue": {
            "number": 3,
            "title": "Crash on start",
            "html_url": "https://github.com/team/app/issues/3",
        },
    }


@pytest.mark.parametrize(
    ("name", "ok"),
    [
        ("team/app", True),
        ("ahmer-shah/baithak.web_2", True),
        ("team", False),
        ("team/app/extra", False),
        ("te am/app", False),
        ("team/..", False),
        ("team/.", False),
    ],
)
def test_valid_repo(name: str, ok: bool) -> None:
    assert valid_repo(name) is ok


class TestSignature:
    body = b'{"zen": "Keep it logically awesome."}'

    def sign(self, secret: str) -> str:
        return "sha256=" + hmac.new(secret.encode(), self.body, hashlib.sha256).hexdigest()

    def test_the_right_secret_passes(self) -> None:
        assert signature_ok("s3cret", self.body, self.sign("s3cret"))

    @pytest.mark.parametrize("header", [None, "", "sha1=abc", "sha256=" + "0" * 64])
    def test_anything_else_fails(self, header: str | None) -> None:
        assert not signature_ok("s3cret", self.body, header)

    def test_another_secret_fails(self) -> None:
        assert not signature_ok("s3cret", self.body, self.sign("other"))


@pytest.mark.parametrize(
    ("event", "payload", "expected"),
    [
        (
            "pull_request",
            pull("opened"),
            "amna opened pull request #12 in team/app: Fix uploads\n"
            "https://github.com/team/app/pull/12",
        ),
        (
            "pull_request",
            pull("ready_for_review"),
            "amna marked ready pull request #12 in team/app: Fix uploads\n"
            "https://github.com/team/app/pull/12",
        ),
        (
            "pull_request",
            pull("closed", merged=True),
            "amna merged pull request #12 in team/app: Fix uploads\n"
            "https://github.com/team/app/pull/12",
        ),
        (
            "pull_request",
            pull("closed", merged=False),
            "amna closed pull request #12 in team/app: Fix uploads\n"
            "https://github.com/team/app/pull/12",
        ),
        (
            "issues",
            issue("reopened"),
            "bilal reopened issue #3 in team/app: Crash on start\n"
            "https://github.com/team/app/issues/3",
        ),
    ],
)
def test_describe_posts_these(event: str, payload: dict[str, Any], expected: str) -> None:
    assert describe(event, payload) == expected


@pytest.mark.parametrize(
    ("event", "payload"),
    [
        ("push", pull("opened")),
        ("pull_request", pull("synchronize")),
        ("issues", issue("labeled")),
        ("pull_request", pull("opened", html_url="https://evil.example/pull/12")),
        ("pull_request", pull("opened", number="12")),
        ("pull_request", pull("opened", title="")),
        ("pull_request", {**pull("opened"), "sender": "amna"}),
        ("pull_request", {**pull("opened"), "repository": None}),
        ("pull_request", "not a dict"),
    ],
)
def test_describe_skips_these(event: str, payload: Any) -> None:
    assert describe(event, payload) is None


def test_repository_is_lowercased_and_empty_when_missing() -> None:
    assert repository({"repository": {"full_name": "Team/App"}}) == "team/app"
    assert repository({}) == ""
