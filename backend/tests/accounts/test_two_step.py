import time
from datetime import timedelta
from typing import Any

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import two_step
from apps.accounts.models import RecoveryCode, TwoStep, User
from apps.accounts.tokens import email_verification_token, encode_uid
from apps.core import totp
from apps.files import crypto
from tests.accounts.factories import PASSWORD, make_user

pytestmark = pytest.mark.django_db

AUTH = "/api/v1/auth/"


def code_for(secret: str, offset: int = 0) -> str:
    return totp.hotp(secret, totp.step_at(time.time()) + offset)


def turn_on(api: APIClient, user: User) -> tuple[str, list[str]]:
    """Sets up two-step sign-in through the API; returns the key and the recovery codes."""
    api.force_authenticate(user)
    secret = api.post(f"{AUTH}two-step/setup/").json()["secret"]
    codes = api.post(f"{AUTH}two-step/enable/", {"code": code_for(secret)}, format="json")
    api.force_authenticate(None)
    mail.outbox.clear()
    return secret, codes.json()["recovery_codes"]


def sign_in(api: APIClient, user: User, password: str = PASSWORD) -> Any:
    return api.post(f"{AUTH}signin/", {"email": user.email, "password": password}, format="json")


def second_step(api: APIClient, code: str) -> Any:
    return api.post(f"{AUTH}signin/two-step/", {"code": code}, format="json")


def signed_in(api: APIClient) -> bool:
    return api.get(f"{AUTH}me/").status_code == 200


@pytest.fixture
def amna() -> User:
    return make_user(username="amna")


class TestSettingUp:
    def test_setup_gives_a_key_and_a_first_code_turns_it_on(
        self, api: APIClient, amna: User
    ) -> None:
        api.force_authenticate(amna)
        setup = api.post(f"{AUTH}two-step/setup/").json()
        assert setup["uri"].startswith("otpauth://totp/Baithak%3Aamna%40example.com?secret=")
        assert api.get(f"{AUTH}two-step/").json() == {"enabled": False, "recovery_codes_left": 0}

        response = api.post(
            f"{AUTH}two-step/enable/", {"code": code_for(setup["secret"])}, format="json"
        )

        assert response.status_code == 200
        assert len(response.json()["recovery_codes"]) == 10
        assert api.get(f"{AUTH}two-step/").json() == {"enabled": True, "recovery_codes_left": 10}
        assert mail.outbox[0].subject == "Two-step sign-in is on"

    def test_the_key_and_codes_are_not_stored_readable(self, api: APIClient, amna: User) -> None:
        secret, codes = turn_on(api, amna)

        row = TwoStep.objects.get(user=amna)
        assert secret.encode() not in bytes(row.secret)
        assert crypto.unseal(bytes(row.secret)) == secret.encode()
        stored = set(RecoveryCode.objects.values_list("code_hash", flat=True))
        assert not stored & set(codes)

    def test_a_wrong_first_code_leaves_it_off(self, api: APIClient, amna: User) -> None:
        api.force_authenticate(amna)
        api.post(f"{AUTH}two-step/setup/")

        response = api.post(f"{AUTH}two-step/enable/", {"code": "000000"}, format="json")

        assert response.status_code == 400
        assert not two_step.is_on(amna)

    def test_an_unconfirmed_email_cannot_turn_it_on(self, api: APIClient) -> None:
        unverified = make_user(email_verified_at=None)
        api.force_authenticate(unverified)

        assert api.post(f"{AUTH}two-step/setup/").status_code == 403

    def test_signed_out_people_get_nothing(self, api: APIClient) -> None:
        for path in ("two-step/setup/", "two-step/enable/", "two-step/disable/"):
            assert api.post(f"{AUTH}{path}", {}, format="json").status_code == 403
        assert api.get(f"{AUTH}two-step/").status_code == 403


class TestSigningIn:
    def test_the_password_alone_does_not_sign_in(self, api: APIClient, amna: User) -> None:
        turn_on(api, amna)

        response = sign_in(api, amna)

        assert response.status_code == 202
        assert response.json()["two_step"] is True
        assert not signed_in(api)

    def test_the_right_code_finishes_signing_in(self, api: APIClient, amna: User) -> None:
        secret, _ = turn_on(api, amna)
        sign_in(api, amna)

        response = second_step(api, code_for(secret, offset=1))

        assert response.status_code == 200
        assert response.json()["email"] == amna.email
        assert signed_in(api)

    def test_a_code_works_only_once(self, api: APIClient, amna: User) -> None:
        secret, _ = turn_on(api, amna)
        code = code_for(secret, offset=1)
        sign_in(api, amna)
        second_step(api, code)
        api.post(f"{AUTH}signout/")
        sign_in(api, amna)

        assert second_step(api, code).status_code == 400
        assert not signed_in(api)

    def test_a_recovery_code_signs_in_once_and_tells_the_owner(
        self, api: APIClient, amna: User
    ) -> None:
        _, codes = turn_on(api, amna)
        sign_in(api, amna)

        assert second_step(api, codes[0].upper().replace("-", " ")).status_code == 200
        assert mail.outbox[-1].subject == "A recovery code was used to sign in to Baithak"
        assert "you have 9 left" in str(mail.outbox[-1].body)
        api.post(f"{AUTH}signout/")
        sign_in(api, amna)
        assert second_step(api, codes[0]).status_code == 400

    def test_no_code_step_without_the_password_first(self, api: APIClient, amna: User) -> None:
        secret, _ = turn_on(api, amna)

        response = second_step(api, code_for(secret))

        assert response.status_code == 400
        assert not signed_in(api)

    def test_the_code_step_times_out(
        self, api: APIClient, amna: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret, _ = turn_on(api, amna)
        sign_in(api, amna)
        later = timezone.now() + timedelta(minutes=6)
        monkeypatch.setattr("apps.accounts.views.timezone.now", lambda: later)

        assert second_step(api, code_for(secret)).status_code == 400
        assert not signed_in(api)

    def test_wrong_codes_climb_the_lockout_ladder(self, api: APIClient, amna: User) -> None:
        secret, _ = turn_on(api, amna)
        sign_in(api, amna)

        answers = [second_step(api, "000000").status_code for _ in range(4)]

        assert answers == [400, 400, 400, 429]
        amna.refresh_from_db()
        assert amna.locked_until is not None
        assert second_step(api, code_for(secret)).status_code == 400

    def test_an_email_link_cannot_skip_the_second_step(self, api: APIClient) -> None:
        person = make_user(username="newcomer", email_verified_at=None)
        old_link = {"uid": encode_uid(person), "token": email_verification_token.make_token(person)}
        person.email_verified_at = timezone.now()
        person.save(update_fields=["email_verified_at"])
        turn_on(api, person)

        response = api.post(f"{AUTH}verify-email/", old_link, format="json")

        assert response.status_code == 400
        assert not signed_in(api)


class TestTurningOff:
    def test_it_needs_the_password_and_a_code(self, api: APIClient, amna: User) -> None:
        secret, _ = turn_on(api, amna)
        api.force_authenticate(amna)

        no_password = api.post(
            f"{AUTH}two-step/disable/",
            {"password": "wrong", "code": code_for(secret)},
            format="json",
        )
        no_code = api.post(
            f"{AUTH}two-step/disable/", {"password": PASSWORD, "code": "000000"}, format="json"
        )
        both = api.post(
            f"{AUTH}two-step/disable/",
            {"password": PASSWORD, "code": code_for(secret, offset=1)},
            format="json",
        )

        assert (no_password.status_code, no_code.status_code, both.status_code) == (400, 400, 204)
        assert not two_step.is_on(amna)
        assert not RecoveryCode.objects.filter(user=amna).exists()
        assert mail.outbox[-1].subject == "Two-step sign-in is off"
        api.force_authenticate(None)
        assert sign_in(api, amna).status_code == 200


class TestRecoveryCodes:
    def test_new_codes_replace_the_old_ones(self, api: APIClient, amna: User) -> None:
        secret, old = turn_on(api, amna)
        api.force_authenticate(amna)

        response = api.post(
            f"{AUTH}two-step/recovery-codes/",
            # The code that turned it on was this step's; it can't be used again.
            {"password": PASSWORD, "code": code_for(secret, offset=1)},
            format="json",
        )

        new = response.json()["recovery_codes"]
        assert not set(new) & set(old)
        assert two_step.check(amna, old[0]) is None
        assert two_step.check(amna, new[0]) == two_step.Used.RECOVERY
        assert mail.outbox[-1].subject == "New recovery codes for Baithak"

    def test_not_while_it_is_off(self, api: APIClient, amna: User) -> None:
        api.force_authenticate(amna)

        response = api.post(
            f"{AUTH}two-step/recovery-codes/", {"password": PASSWORD, "code": "1"}, format="json"
        )

        assert response.status_code == 400
