import base64
import hashlib
import time
import urllib.parse
from collections.abc import Iterator
from typing import Any

import pytest
from django.conf import settings
from django.test import override_settings
from joserfc import jwt
from joserfc.jwk import RSAKey
from rest_framework.test import APIClient

from apps.accounts import oidc
from apps.accounts.models import Device, ExternalIdentity, User
from tests.accounts.factories import PASSWORD, make_user
from tests.accounts.test_two_step import turn_on

pytestmark = pytest.mark.django_db

AUTH = "/api/v1/auth/"
CLIENT_ID = "baithak-test.apps.googleusercontent.com"
KEY = RSAKey.generate_key(2048, parameters={"kid": "google-1", "alg": "RS256", "use": "sig"})
OTHER_KEY = RSAKey.generate_key(2048, parameters={"kid": "google-1", "alg": "RS256"})


class FakeGoogle:
    """Stands in for Google's token and key endpoints."""

    def __init__(self) -> None:
        self.claims: dict[str, Any] = {}
        self.signing_key = KEY
        self.challenge = ""
        self.nonce = ""
        self.exchanges: list[dict[str, str]] = []

    def token(self, nonce: str) -> str:
        now = int(time.time())
        claims = {
            "iss": "https://accounts.google.com",
            "aud": CLIENT_ID,
            "sub": "google-sub-1",
            "email": "amna@example.com",
            "email_verified": True,
            "name": "Amna Khan",
            "iat": now,
            "exp": now + 3600,
            "nonce": nonce,
        } | self.claims
        return jwt.encode({"alg": "RS256", "kid": "google-1"}, claims, self.signing_key)

    def fetch(self, url: str, form: dict[str, str] | None = None) -> Any:
        if url.endswith("/certs"):
            return {"keys": [KEY.as_dict(private=False)]}
        assert form is not None
        self.exchanges.append(form)
        digest = hashlib.sha256(form["code_verifier"].encode()).digest()
        assert base64.urlsafe_b64encode(digest).rstrip(b"=").decode() == self.challenge
        return {"id_token": self.token(self.nonce), "access_token": "unused"}


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGoogle]:
    fake = FakeGoogle()
    monkeypatch.setattr(oidc, "_fetch_json", fake.fetch)
    with override_settings(GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET="test-secret"):
        yield fake


def go_to_google(api: APIClient, google: FakeGoogle, next_path: str = "/w/team") -> dict[str, str]:
    response = api.get(f"{AUTH}oidc/google/start/", {"next": next_path})
    assert response.status_code == 302
    query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(response["Location"]).query))
    google.challenge = query["code_challenge"]
    google.nonce = query["nonce"]
    return query


def come_back(api: APIClient, state: str, **extra: str) -> Any:
    return api.get(
        f"{AUTH}oidc/google/callback/", {"code": "one-time-code", "state": state} | extra
    )


def signed_in_as(api: APIClient) -> str | None:
    response = api.get(f"{AUTH}me/")
    return response.json()["email"] if response.status_code == 200 else None


class TestStarting:
    def test_it_sends_the_person_to_google_with_pkce_state_and_nonce(
        self, api: APIClient, google: FakeGoogle
    ) -> None:
        response = api.get(f"{AUTH}oidc/google/start/")
        location = urllib.parse.urlsplit(response["Location"])
        query = dict(urllib.parse.parse_qsl(location.query))

        assert f"{location.scheme}://{location.netloc}{location.path}" == (
            "https://accounts.google.com/o/oauth2/v2/auth"
        )
        assert query["client_id"] == CLIENT_ID
        assert query["redirect_uri"] == f"{settings.FRONTEND_URL}/api/v1/auth/oidc/google/callback/"
        assert query["scope"] == "openid email profile"
        assert query["code_challenge_method"] == "S256"
        assert len(query["state"]) >= 40
        assert len(query["nonce"]) >= 40

    def test_the_button_shows_only_when_google_is_set_up(
        self, api: APIClient, google: FakeGoogle
    ) -> None:
        assert api.get(f"{AUTH}config/").json()["providers"] == ["google"]
        with override_settings(GOOGLE_CLIENT_ID=""):
            assert api.get(f"{AUTH}config/").json()["providers"] == []
            assert api.get(f"{AUTH}oidc/google/start/").status_code == 404
        assert api.get(f"{AUTH}oidc/github/start/").status_code == 404


class TestComingBack:
    def test_a_new_person_gets_a_verified_account_and_lands_where_they_were_going(
        self, api: APIClient, google: FakeGoogle
    ) -> None:
        state = go_to_google(api, google)["state"]

        response = come_back(api, state)

        assert response.status_code == 302
        assert response["Location"] == f"{settings.FRONTEND_URL}/w/team"
        assert signed_in_as(api) == "amna@example.com"
        user = User.objects.get(email="amna@example.com")
        assert (user.username, user.display_name, user.email_verified) == (
            "amna",
            "Amna Khan",
            True,
        )
        assert not user.has_usable_password()
        assert ExternalIdentity.objects.get(user=user).subject == "google-sub-1"
        assert Device.objects.filter(user=user).count() == 1

    def test_an_existing_verified_account_is_linked_and_keeps_its_password(
        self, api: APIClient, google: FakeGoogle
    ) -> None:
        amna = make_user(username="amna", email="amna@example.com")
        state = go_to_google(api, google)["state"]

        come_back(api, state)

        amna.refresh_from_db()
        assert signed_in_as(api) == "amna@example.com"
        assert amna.check_password(PASSWORD)
        assert ExternalIdentity.objects.filter(user=amna).exists()

    def test_an_unverified_account_with_the_address_loses_its_password_and_sessions(
        self, api: APIClient, google: FakeGoogle
    ) -> None:
        squatter = make_user(username="squatter", email="amna@example.com", email_verified_at=None)
        their_browser = APIClient()
        their_browser.post(
            f"{AUTH}signin/", {"email": "amna@example.com", "password": PASSWORD}, format="json"
        )
        state = go_to_google(api, google)["state"]

        come_back(api, state)

        squatter.refresh_from_db()
        assert not squatter.has_usable_password()
        assert squatter.email_verified
        assert signed_in_as(their_browser) is None
        assert signed_in_as(api) == "amna@example.com"

    def test_the_second_time_the_link_is_used_even_if_the_email_changed(
        self, api: APIClient, google: FakeGoogle
    ) -> None:
        come_back(api, go_to_google(api, google)["state"])
        api.post(f"{AUTH}signout/")
        google.claims = {"email": "amna.new@example.com"}

        come_back(api, go_to_google(api, google)["state"])

        assert signed_in_as(api) == "amna@example.com"
        assert User.objects.count() == 1

    def test_a_taken_handle_gets_digits(self, api: APIClient, google: FakeGoogle) -> None:
        make_user(username="amna", email="someone.else@example.com")

        come_back(api, go_to_google(api, google)["state"])

        handle = User.objects.get(email="amna@example.com").username
        assert handle.startswith("amna")
        assert handle != "amna"

    def test_two_step_is_not_asked_after_google(self, api: APIClient, google: FakeGoogle) -> None:
        amna = make_user(username="amna", email="amna@example.com")
        turn_on(APIClient(), amna)

        come_back(api, go_to_google(api, google)["state"])

        assert signed_in_as(api) == "amna@example.com"


class TestRefusing:
    def refused_with(self, response: Any, reason: str) -> bool:
        return bool(response["Location"] == f"{settings.FRONTEND_URL}/signin?error={reason}")

    def test_an_unverified_google_address(self, api: APIClient, google: FakeGoogle) -> None:
        google.claims = {"email_verified": False}

        response = come_back(api, go_to_google(api, google)["state"])

        assert self.refused_with(response, "unverified")
        assert signed_in_as(api) is None
        assert not User.objects.exists()

    def test_a_state_this_browser_never_started(self, api: APIClient, google: FakeGoogle) -> None:
        go_to_google(api, google)

        response = come_back(api, "made-up-state")

        assert self.refused_with(response, "failed")
        assert google.exchanges == []

    def test_a_state_used_twice(self, api: APIClient, google: FakeGoogle) -> None:
        state = go_to_google(api, google)["state"]
        come_back(api, state)
        api.post(f"{AUTH}signout/")

        assert self.refused_with(come_back(api, state), "failed")

    @pytest.mark.parametrize(
        "claims",
        [
            {"aud": "someone-elses-app"},
            {"iss": "https://evil.example"},
            {"exp": int(time.time()) - 3600},
            {"nonce": "a-different-nonce"},
        ],
    )
    def test_a_token_that_does_not_check_out(
        self, api: APIClient, google: FakeGoogle, claims: dict[str, Any]
    ) -> None:
        google.claims = claims

        response = come_back(api, go_to_google(api, google)["state"])

        assert self.refused_with(response, "failed")
        assert signed_in_as(api) is None

    def test_a_token_signed_by_another_key(self, api: APIClient, google: FakeGoogle) -> None:
        google.signing_key = OTHER_KEY

        response = come_back(api, go_to_google(api, google)["state"])

        assert self.refused_with(response, "failed")

    def test_cancelled_at_google(self, api: APIClient, google: FakeGoogle) -> None:
        state = go_to_google(api, google)["state"]

        response = come_back(api, state, error="access_denied")

        assert self.refused_with(response, "cancelled")

    def test_a_deactivated_or_locked_account(self, api: APIClient, google: FakeGoogle) -> None:
        amna = make_user(username="amna", email="amna@example.com")
        come_back(api, go_to_google(api, google)["state"])
        api.post(f"{AUTH}signout/")
        amna.is_active = False
        amna.save()

        response = come_back(api, go_to_google(api, google)["state"])

        assert self.refused_with(response, "inactive")
        assert signed_in_as(api) is None

    @pytest.mark.parametrize("next_path", ["//evil.example/x", "https://evil.example", "/\\evil"])
    def test_it_never_lands_on_another_site(
        self, api: APIClient, google: FakeGoogle, next_path: str
    ) -> None:
        state = go_to_google(api, google, next_path)["state"]

        response = come_back(api, state)

        assert response["Location"] == f"{settings.FRONTEND_URL}/"


class TestWithoutAPassword:
    def test_deleting_the_account_is_confirmed_with_the_email(
        self, api: APIClient, google: FakeGoogle
    ) -> None:
        come_back(api, go_to_google(api, google)["state"])

        wrong = api.post(f"{AUTH}delete-account/", {"email": "nope@example.com"}, format="json")
        right = api.post(f"{AUTH}delete-account/", {"email": "Amna@Example.com "}, format="json")

        assert (wrong.status_code, right.status_code) == (400, 204)
        assert not User.objects.exists()

    def test_two_step_needs_a_password_first(self, api: APIClient, google: FakeGoogle) -> None:
        come_back(api, go_to_google(api, google)["state"])

        assert api.post(f"{AUTH}two-step/setup/").status_code == 403
        assert api.get(f"{AUTH}me/").json()["has_password"] is False
