from __future__ import annotations

import io
import json
from typing import Any
from unittest import mock

import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts import captcha
from apps.accounts.captcha import Verdict
from apps.accounts.models import User
from config.settings import base
from tests.accounts.factories import PASSWORD, make_user

V3 = {"RECAPTCHA_V3_SECRET_KEY": "v3-secret", "RECAPTCHA_V2_SECRET_KEY": ""}
BOTH = {"RECAPTCHA_V3_SECRET_KEY": "v3-secret", "RECAPTCHA_V2_SECRET_KEY": "v2-secret"}
NO_IP_THROTTLE = {**base.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"auth": None}}
V2_ONLY = {"RECAPTCHA_V3_SECRET_KEY": "", "RECAPTCHA_V2_SECRET_KEY": "v2-secret"}


def google(**answer: Any) -> mock._patch[mock.MagicMock]:
    reply = {"success": True, "hostname": "web.test", "action": "signin", "score": 0.9} | answer
    return mock.patch.object(captcha, "_siteverify", return_value=reply)


class TestPasswordHashing:
    def test_argon2id_hashes_new_passwords(self) -> None:
        with override_settings(PASSWORD_HASHERS=base.PASSWORD_HASHERS):
            hashed = make_password(PASSWORD)

        assert hashed.startswith("argon2$argon2id$")

    def test_older_pbkdf2_hashes_still_verify_and_are_upgraded(self) -> None:
        with override_settings(PASSWORD_HASHERS=base.PASSWORD_HASHERS):
            old = make_password(PASSWORD, hasher="pbkdf2_sha256")
            upgraded: list[str] = []

            assert check_password(PASSWORD, old, setter=upgraded.append)
            assert len(upgraded) == 1


class TestCaptchaVerdicts:
    def test_off_without_keys(self) -> None:
        assert captcha.verify({}, "signin", None) == Verdict.ALLOW

    @override_settings(**V3)
    def test_good_v3_score_passes(self) -> None:
        with google():
            assert captcha.verify({"captcha": "t"}, "signin", "1.2.3.4") == Verdict.ALLOW

    @override_settings(**BOTH)
    @pytest.mark.parametrize(
        "answer",
        [{"score": 0.1}, {"action": "signup"}, {"hostname": "evil.test"}, {"success": False}],
    )
    def test_doubtful_v3_asks_for_the_checkbox(self, answer: dict[str, Any]) -> None:
        with google(**answer):
            assert captcha.verify({"captcha": "t"}, "signin", None) == Verdict.CHALLENGE

    @override_settings(**V3)
    def test_doubtful_v3_without_v2_is_denied(self) -> None:
        with google(score=0.1):
            assert captcha.verify({"captcha": "t"}, "signin", None) == Verdict.DENY

    @override_settings(**BOTH)
    def test_missing_token_asks_for_the_checkbox(self) -> None:
        assert captcha.verify({}, "signin", None) == Verdict.CHALLENGE

    @override_settings(**V2_ONLY)
    def test_v2_only_asks_for_the_checkbox_first(self) -> None:
        assert captcha.verify({}, "signin", None) == Verdict.CHALLENGE

    @override_settings(**BOTH)
    def test_solved_checkbox_passes(self) -> None:
        with google() as siteverify:
            assert captcha.verify({"captcha_v2": "t"}, "signin", None) == Verdict.ALLOW
        assert siteverify.call_args.args[0] == "v2-secret"

    @override_settings(**BOTH)
    def test_bad_checkbox_is_denied(self) -> None:
        with google(success=False):
            assert captcha.verify({"captcha_v2": "t"}, "signin", None) == Verdict.DENY

    @override_settings(**BOTH)
    @pytest.mark.parametrize("data", [{"captcha": "t"}, {"captcha_v2": "t"}])
    def test_google_down_lets_the_request_through(self, data: dict[str, str]) -> None:
        with mock.patch.object(captcha, "_siteverify", return_value=None):
            assert captcha.verify(data, "signin", None) == Verdict.ALLOW


class TestSiteverify:
    def test_posts_secret_token_and_ip(self) -> None:
        reply = io.BytesIO(json.dumps({"success": True}).encode())
        with mock.patch("urllib.request.urlopen", return_value=reply) as urlopen:
            result = captcha._siteverify("secret", "token", "1.2.3.4")

        assert result == {"success": True}
        sent = urlopen.call_args.args[0]
        assert sent.full_url == captcha.VERIFY_URL
        assert sent.data == b"secret=secret&response=token&remoteip=1.2.3.4"

    def test_network_error_is_none(self) -> None:
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            assert captcha._siteverify("secret", "token", None) is None


@pytest.mark.django_db
class TestAuthEndpointsUseTheGuards:
    @override_settings(**BOTH)
    def test_doubtful_sign_in_asks_for_the_checkbox(self, api: APIClient) -> None:
        make_user(email="amna@example.com")
        with google(score=0.1):
            response = api.post(
                "/api/v1/auth/signin/",
                {"email": "amna@example.com", "password": PASSWORD, "captcha": "t"},
                format="json",
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Please confirm you are a person.", "captcha": "v2"}

    @override_settings(**V3)
    def test_denied_sign_up_creates_nothing(self, api: APIClient) -> None:
        with google(score=0.1):
            response = api.post(
                "/api/v1/auth/signup/",
                {"email": "a@example.com", "username": "aa", "password": PASSWORD},
                format="json",
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "The person check failed. Try it again."}
        assert User.objects.count() == 0

    def test_honeypot_sign_up_looks_fine_but_creates_nothing(self, api: APIClient) -> None:
        response = api.post(
            "/api/v1/auth/signup/",
            {"email": "bot@example.com", "username": "bot", "password": PASSWORD, "website": "x"},
            format="json",
        )

        assert response.status_code == 202
        assert User.objects.count() == 0

    def test_honeypot_sign_in_is_refused_even_with_the_right_password(self, api: APIClient) -> None:
        make_user(email="amna@example.com")

        response = api.post(
            "/api/v1/auth/signin/",
            {"email": "amna@example.com", "password": PASSWORD, "website": "x"},
            format="json",
        )

        assert response.status_code == 400

    def test_honeypot_reset_sends_nothing(self, api: APIClient) -> None:
        from django.core import mail

        make_user(email="amna@example.com")

        response = api.post(
            "/api/v1/auth/password-reset/",
            {"email": "amna@example.com", "website": "x"},
            format="json",
        )

        assert response.status_code == 202
        assert mail.outbox == []

    @override_settings(
        REST_FRAMEWORK={**base.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"auth": None}}
    )
    def test_five_wrong_passwords_lock_the_account_from_any_ip(self, api: APIClient) -> None:
        make_user(email="amna@example.com")
        wrong = {"email": "amna@example.com", "password": "wrong-password"}
        codes = [
            api.post(
                "/api/v1/auth/signin/", wrong, format="json", REMOTE_ADDR=f"10.0.0.{n}"
            ).status_code
            for n in range(5)
        ]

        right = api.post(
            "/api/v1/auth/signin/",
            {"email": "amna@example.com", "password": PASSWORD},
            format="json",
            REMOTE_ADDR="10.0.0.99",
        )

        assert codes == [400] * 5
        assert right.status_code == 429

    def test_a_good_sign_in_clears_earlier_failures(self, api: APIClient) -> None:
        make_user(email="amna@example.com")
        wrong = {"email": "amna@example.com", "password": "wrong-password"}
        right = {"email": "amna@example.com", "password": PASSWORD}
        for _ in range(4):
            api.post("/api/v1/auth/signin/", wrong, format="json")
        api.post("/api/v1/auth/signin/", right, format="json")
        api.post("/api/v1/auth/signout/")

        after = [
            api.post("/api/v1/auth/signin/", wrong, format="json").status_code for _ in range(4)
        ]

        assert after == [400] * 4


@pytest.mark.django_db
@override_settings(RECAPTCHA_V3_SITE_KEY="site-3", RECAPTCHA_V2_SITE_KEY="site-2")
def test_config_gives_the_public_site_keys_only(api: APIClient) -> None:
    response = api.get("/api/v1/auth/config/")

    assert response.json() == {"recaptcha_v3_site_key": "site-3", "recaptcha_v2_site_key": "site-2"}


def test_failure_counter_survives_expiring_between_add_and_incr() -> None:
    from django.core.cache import cache

    from apps.accounts import guards

    with mock.patch.object(cache, "incr", side_effect=ValueError("gone")):
        guards.note_failure("amna@example.com")

    assert not guards.account_locked("amna@example.com")
    assert cache.get(guards._failures_key("amna@example.com")) == 1


@pytest.mark.django_db
class TestSecurityHeaders:
    def test_api_responses_forbid_loading_anything(self, api: APIClient) -> None:
        response = api.get("/api/v1/auth/me/")

        assert response["Content-Security-Policy"].startswith("default-src 'none'")
        assert response["Cache-Control"] == "no-store"

    def test_other_responses_are_left_alone(self, api: APIClient) -> None:
        response = api.get("/health/")

        assert "Content-Security-Policy" not in response
