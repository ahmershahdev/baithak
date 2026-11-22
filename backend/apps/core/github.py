"""GitHub webhooks: checking a delivery's signature and saying what it was about.

Signatures follow GitHub's docs ("Validating webhook deliveries"): X-Hub-Signature-256 is
"sha256=" and the HMAC-SHA256 of the raw body, keyed with the webhook's secret.
"""

import hashlib
import hmac
import re
from typing import Any

_REPO = re.compile(r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")
_PREFIX = "sha256="

# event -> (payload key of the item, what to call it, action -> verb). Anything else is skipped.
_EVENTS: dict[str, tuple[str, str, dict[str, str]]] = {
    "pull_request": (
        "pull_request",
        "pull request",
        {"opened": "opened", "reopened": "reopened", "ready_for_review": "marked ready"},
    ),
    "issues": ("issue", "issue", {"opened": "opened", "closed": "closed", "reopened": "reopened"}),
}


def valid_repo(name: str) -> bool:
    """owner/name as GitHub allows them ("." and ".." are not names)."""
    return bool(_REPO.match(name)) and name.split("/")[1] not in (".", "..")


def signature_ok(secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith(_PREFIX):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    # Constant time, so the right signature can't be found a character at a time.
    return hmac.compare_digest(expected, header[len(_PREFIX) :])


def _get(data: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _text(data: Any, *path: str) -> str:
    value = _get(data, *path)
    return value if isinstance(value, str) else ""


def repository(payload: Any) -> str:
    """The delivery's owner/name, lowercased like stored ones; empty if it has none."""
    return _text(payload, "repository", "full_name").lower()


def describe(event: str, payload: Any) -> str | None:
    """The message to post for a delivery: "amna merged pull request #12 in team/app: Title"
    and its link. None for events and actions we don't post, and for payloads missing a part."""
    if event not in _EVENTS:
        return None
    key, noun, verbs = _EVENTS[event]
    action = _text(payload, "action")
    if event == "pull_request" and action == "closed":
        verb = "merged" if _get(payload, key, "merged") is True else "closed"
    else:
        verb = verbs.get(action, "")
    who = _text(payload, "sender", "login")
    repo = _text(payload, "repository", "full_name")
    title = _text(payload, key, "title")
    url = _text(payload, key, "html_url")
    number = _get(payload, key, "number")
    # Only links into GitHub itself go out, because the channel shows them as links.
    if not (verb and who and repo and title and url.startswith("https://github.com/")):
        return None
    if not isinstance(number, int):
        return None
    return f"{who} {verb} {noun} #{number} in {repo}: {title}\n{url}"
