"""Signing in through an OpenID Connect provider: the authorization code flow with PKCE, state
and nonce (OpenID Connect Core 1.0, section 3.1; RFC 7636). Provider-neutral, so a workspace's
own identity provider can use it too (docs/architecture.md, Signing in with Google)."""

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

# How long the person has at the provider before the round trip is refused.
PENDING_SECONDS = 10 * 60
KEYS_SECONDS = 60 * 60
HTTP_TIMEOUT = 10
# Clock difference allowed when checking the token's times.
LEEWAY_SECONDS = 60
ALGORITHMS = ["RS256", "ES256"]


class Refused(Exception):
    """The round trip can't sign anyone in: wrong state, failed exchange or a bad token."""


@dataclass(frozen=True)
class Provider:
    key: str
    issuers: tuple[str, ...]
    client_id: str
    client_secret: str
    authorize_url: str
    exchange_url: str
    jwks_url: str
    scopes: str = "openid email profile"


def google() -> Provider | None:
    if not settings.GOOGLE_CLIENT_ID:
        return None
    return Provider(
        key="google",
        # Google issues tokens under both spellings (developers.google.com/identity/openid-connect).
        issuers=("https://accounts.google.com", "accounts.google.com"),
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        exchange_url="https://oauth2.googleapis.com/token",
        jwks_url="https://www.googleapis.com/oauth2/v3/certs",
    )


def redirect_uri(provider: Provider) -> str:
    return f"{settings.FRONTEND_URL}/api/v1/auth/oidc/{provider.key}/callback/"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def start(request: HttpRequest, provider: Provider, next_path: str) -> str:
    """The provider's sign-in address. What comes back is checked against this session."""
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    request.session[f"oidc:{state}"] = {
        "provider": provider.key,
        "nonce": nonce,
        "verifier": verifier,
        "next": next_path,
        "until": time.time() + PENDING_SECONDS,
    }
    query = {
        "response_type": "code",
        "client_id": provider.client_id,
        "redirect_uri": redirect_uri(provider),
        "scope": provider.scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{provider.authorize_url}?{urllib.parse.urlencode(query)}"


def _fetch_json(url: str, form: dict[str, str] | None = None) -> Any:
    data = urllib.parse.urlencode(form).encode() if form is not None else None
    # Only the provider's own fixed https addresses are ever fetched here.
    request = urllib.request.Request(url, data=data, headers={"Accept": "application/json"})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:  # noqa: S310  # nosec B310
            return json.loads(response.read())
    except (OSError, ValueError) as error:
        raise Refused(f"Could not reach the provider: {error}") from error


def _keys(provider: Provider, *, fresh: bool = False) -> KeySet:
    cache_key = f"oidc-keys:{provider.jwks_url}"
    keys = None if fresh else cache.get(cache_key)
    if keys is None:
        keys = _fetch_json(provider.jwks_url)
        cache.set(cache_key, keys, KEYS_SECONDS)
    return KeySet.import_key_set(keys)


def verify(provider: Provider, id_token: str, nonce: str) -> dict[str, Any]:
    """The ID token's claims, once its signature, issuer, audience, times and nonce check out."""
    try:
        try:
            token = jwt.decode(id_token, _keys(provider), algorithms=ALGORITHMS)
        except JoseError:
            # The provider may have rotated its keys since they were cached.
            token = jwt.decode(id_token, _keys(provider, fresh=True), algorithms=ALGORITHMS)
        claims = token.claims
        jwt.JWTClaimsRegistry(
            leeway=LEEWAY_SECONDS,
            iss={"essential": True, "values": list(provider.issuers)},
            aud={"essential": True, "value": provider.client_id},
            exp={"essential": True},
            sub={"essential": True},
            nonce={"essential": True, "value": nonce},
        ).validate(claims)
    except (JoseError, ValueError) as error:
        raise Refused(f"The sign-in token is not valid: {error}") from error
    audiences = claims["aud"] if isinstance(claims["aud"], list) else [claims["aud"]]
    if len(audiences) > 1 and claims.get("azp") != provider.client_id:
        raise Refused("The sign-in token was issued to another app.")
    return claims


def finish(
    request: HttpRequest, provider: Provider, code: str, state: str
) -> tuple[dict[str, Any], str]:
    """The verified claims and the page to land on. Each state works once."""
    pending = request.session.pop(f"oidc:{state}", None)
    if (
        not isinstance(pending, dict)
        or pending.get("provider") != provider.key
        or pending.get("until", 0) < time.time()
    ):
        raise Refused("This sign-in was not started here, or it took too long.")
    tokens = _fetch_json(
        provider.exchange_url,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri(provider),
            "client_id": provider.client_id,
            "client_secret": provider.client_secret,
            "code_verifier": pending["verifier"],
        },
    )
    if not isinstance(tokens, dict) or not isinstance(tokens.get("id_token"), str):
        raise Refused("The provider did not send a sign-in token.")
    return verify(provider, tokens["id_token"], pending["nonce"]), pending["next"]
