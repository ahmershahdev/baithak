"""Google reCAPTCHA: v3 scores every auth request, v2 is the checkbox shown when v3 doubts.

The client sends `captcha` (a v3 token) and, after a challenge, `captcha_v2`. With no secrets
configured (local development, tests) every request passes.
"""

import json
import logging
import urllib.parse
import urllib.request
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from django.conf import settings

log = logging.getLogger(__name__)

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


class Verdict(StrEnum):
    ALLOW = "allow"
    CHALLENGE = "challenge"
    DENY = "deny"


def _siteverify(secret: str, token: str, remote_ip: str | None) -> dict[str, Any] | None:
    body = {"secret": secret, "response": token}
    if remote_ip:
        body["remoteip"] = remote_ip
    request = urllib.request.Request(
        VERIFY_URL, data=urllib.parse.urlencode(body).encode(), method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            result: dict[str, Any] = json.load(response)
            return result
    except (OSError, ValueError):
        log.warning("reCAPTCHA verification could not reach Google")
        return None


def _expected_host() -> str | None:
    return urlparse(settings.FRONTEND_URL).hostname


def verify(data: Any, action: str, remote_ip: str | None) -> Verdict:
    v3_secret = settings.RECAPTCHA_V3_SECRET_KEY
    v2_secret = settings.RECAPTCHA_V2_SECRET_KEY
    if not v3_secret and not v2_secret:
        return Verdict.ALLOW

    v2_token = data.get("captcha_v2")
    if v2_token and v2_secret:
        result = _siteverify(v2_secret, str(v2_token), remote_ip)
        # Google unreachable: let the request through; throttles and the per-account limit
        # still apply, and blocking every sign-in during an outage is worse.
        if result is None:
            return Verdict.ALLOW
        if result.get("success") and result.get("hostname") == _expected_host():
            return Verdict.ALLOW
        return Verdict.DENY

    doubt = Verdict.CHALLENGE if v2_secret else Verdict.DENY
    v3_token = data.get("captcha")
    if not v3_secret or not v3_token:
        return doubt
    result = _siteverify(v3_secret, str(v3_token), remote_ip)
    if result is None:
        return Verdict.ALLOW
    trusted = (
        bool(result.get("success"))
        and result.get("action") == action
        and result.get("hostname") == _expected_host()
        and float(result.get("score", 0)) >= settings.RECAPTCHA_V3_MIN_SCORE
    )
    return Verdict.ALLOW if trusted else doubt
