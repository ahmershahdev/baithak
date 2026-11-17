import re
from urllib.parse import parse_qs, urlparse

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts import tasks
from apps.accounts.models import User
from apps.accounts.tokens import email_verification_token, encode_uid, password_reset_token
from tests.accounts.factories import PASSWORD, make_user

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "another-long-password-77"


def link_params(body: str) -> dict[str, str]:
    match = re.search(r"http://web\.test/\S+", body)
    assert match is not None
    query = parse_qs(urlparse(match.group(0)).query)
    return {"uid": query["uid"][0], "token": query["token"][0]}


def sign_up(api: APIClient, **overrides: str) -> tuple[int, dict[str, object]]:
    payload = {
        "email": "Amna@Example.com",
        "username": "amna",
        "display_name": "Amna Khan",
        "password": PASSWORD,
    } | overrides
    response = api.post("/api/v1/auth/signup/", payload, format="json")
    return response.status_code, response.json()


class TestSignUp:
    def test_creates_an_unverified_user_and_sends_a_link(
        self, api: APIClient, django_capture_on_commit_callbacks: object
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            status, body = sign_up(api)

        assert status == 202
        user = User.objects.get()
        assert user.email == "amna@example.com"
        assert user.username == "amna"
        assert not user.email_verified
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["amna@example.com"]
        assert "/verify-email?" in mail.outbox[0].body
        assert "detail" in body

    def test_does_not_sign_in(self, api: APIClient) -> None:
        sign_up(api)

        assert api.get("/api/v1/auth/me/").status_code == 403

    def test_taken_email_answers_the_same_and_mails_the_owner(
        self, api: APIClient, django_capture_on_commit_callbacks: object
    ) -> None:
        owner = make_user(email="amna@example.com", username="amna")

        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            status, body = sign_up(api, username="someone-else")

        assert status == 202
        assert body == {"detail": "If the address can be used, an email is on its way."}
        assert User.objects.count() == 1
        assert mail.outbox[0].to == [owner.email]
        assert mail.outbox[0].subject == "You already have a Baithak account"

    def test_taken_handle_is_an_error(self, api: APIClient) -> None:
        make_user(username="amna")

        status, body = sign_up(api, username="AMNA")

        assert status == 400
        assert body == {"username": ["This handle is taken."]}

    @pytest.mark.parametrize("username", ["a", "-amna", "amna khan", "amna@x", "x" * 31])
    def test_rejects_handles_a_mention_cannot_use(self, api: APIClient, username: str) -> None:
        status, body = sign_up(api, username=username)

        assert status == 400
        assert "username" in body

    def test_rejects_weak_passwords(self, api: APIClient) -> None:
        status, body = sign_up(api, password="password")

        assert status == 400
        assert "password" in body
        assert User.objects.count() == 0


class TestVerifyEmail:
    def test_link_from_the_email_verifies_and_signs_in(
        self, api: APIClient, django_capture_on_commit_callbacks: object
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            sign_up(api)

        response = api.post(
            "/api/v1/auth/verify-email/", link_params(str(mail.outbox[0].body)), format="json"
        )

        assert response.status_code == 200
        assert response.json()["email_verified"] is True
        assert api.get("/api/v1/auth/me/").json()["username"] == "amna"

    def test_link_works_once(self, api: APIClient) -> None:
        user = make_user(email_verified_at=None)
        params = {"uid": encode_uid(user), "token": email_verification_token.make_token(user)}

        assert api.post("/api/v1/auth/verify-email/", params, format="json").status_code == 200
        second = api.post("/api/v1/auth/verify-email/", params, format="json")

        assert second.status_code == 400

    @pytest.mark.parametrize("uid", ["not-base64!", "MTIzNDU2Nzg5"])
    def test_bad_uid_is_rejected(self, api: APIClient, uid: str) -> None:
        response = api.post(
            "/api/v1/auth/verify-email/", {"uid": uid, "token": "x-y"}, format="json"
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "This link is not valid or has expired."}

    def test_resend_mails_an_unverified_person(self, api: APIClient) -> None:
        user = make_user(email_verified_at=None)
        api.force_authenticate(user)

        response = api.post("/api/v1/auth/verify-email/resend/")

        assert response.status_code == 202
        assert len(mail.outbox) == 1

    def test_resend_does_nothing_when_verified(self, api: APIClient) -> None:
        api.force_authenticate(make_user())

        assert api.post("/api/v1/auth/verify-email/resend/").status_code == 202
        assert mail.outbox == []


class TestSignIn:
    def test_signs_in_with_any_email_case(self, api: APIClient) -> None:
        make_user(email="bilal@example.com", username="bilal")

        response = api.post(
            "/api/v1/auth/signin/",
            {"email": "Bilal@Example.com", "password": PASSWORD},
            format="json",
        )

        assert response.status_code == 200
        assert response.json()["username"] == "bilal"
        assert api.get("/api/v1/auth/me/").status_code == 200

    @pytest.mark.parametrize(
        ("email", "password"),
        [("bilal@example.com", "wrong-password"), ("nobody@example.com", PASSWORD)],
    )
    def test_wrong_email_or_password_get_the_same_answer(
        self, api: APIClient, email: str, password: str
    ) -> None:
        make_user(email="bilal@example.com")

        response = api.post(
            "/api/v1/auth/signin/", {"email": email, "password": password}, format="json"
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "The email or password is wrong."}

    def test_inactive_people_cannot_sign_in(self, api: APIClient) -> None:
        make_user(email="bilal@example.com", is_active=False)

        response = api.post(
            "/api/v1/auth/signin/",
            {"email": "bilal@example.com", "password": PASSWORD},
            format="json",
        )

        assert response.status_code == 400

    def test_is_throttled_after_ten_attempts(self, api: APIClient) -> None:
        payload = {"email": "x@example.com", "password": "wrong"}
        codes = [
            api.post("/api/v1/auth/signin/", payload, format="json").status_code for _ in range(11)
        ]

        assert codes[:10] == [400] * 10
        assert codes[10] == 429

    def test_needs_a_csrf_token(self) -> None:
        make_user(email="bilal@example.com")
        api = APIClient(enforce_csrf_checks=True)
        payload = {"email": "bilal@example.com", "password": PASSWORD}

        without = api.post("/api/v1/auth/signin/", payload, format="json")
        api.get("/api/v1/auth/csrf/")
        token = api.cookies["csrftoken"].value
        with_token = api.post(
            "/api/v1/auth/signin/", payload, format="json", headers={"X-CSRFToken": token}
        )

        assert without.status_code == 403
        assert with_token.status_code == 200

    def test_sign_out_ends_the_session(self, api: APIClient) -> None:
        make_user(email="bilal@example.com")
        api.post(
            "/api/v1/auth/signin/",
            {"email": "bilal@example.com", "password": PASSWORD},
            format="json",
        )

        assert api.post("/api/v1/auth/signout/").status_code == 204
        assert api.get("/api/v1/auth/me/").status_code == 403


class TestPasswordReset:
    def test_known_email_gets_a_link_that_sets_the_password(self, api: APIClient) -> None:
        user = make_user(email="chanda@example.com")

        response = api.post(
            "/api/v1/auth/password-reset/", {"email": "Chanda@example.com"}, format="json"
        )
        params = link_params(str(mail.outbox[0].body))
        confirm = api.post(
            "/api/v1/auth/password-reset/confirm/",
            params | {"password": NEW_PASSWORD},
            format="json",
        )

        assert response.status_code == 202
        assert confirm.status_code == 204
        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)

    def test_unknown_email_gets_the_same_answer_and_no_mail(self, api: APIClient) -> None:
        response = api.post(
            "/api/v1/auth/password-reset/", {"email": "nobody@example.com"}, format="json"
        )

        assert response.status_code == 202
        assert response.json() == {"detail": "If the address can be used, an email is on its way."}
        assert mail.outbox == []

    def test_link_stops_working_after_use(self, api: APIClient) -> None:
        user = make_user()
        params = {"uid": encode_uid(user), "token": password_reset_token.make_token(user)}

        first = api.post(
            "/api/v1/auth/password-reset/confirm/",
            params | {"password": NEW_PASSWORD},
            format="json",
        )
        second = api.post(
            "/api/v1/auth/password-reset/confirm/",
            params | {"password": "yet-another-password-9"},
            format="json",
        )

        assert first.status_code == 204
        assert second.status_code == 400

    def test_weak_new_password_is_rejected(self, api: APIClient) -> None:
        user = make_user()
        params = {"uid": encode_uid(user), "token": password_reset_token.make_token(user)}

        response = api.post(
            "/api/v1/auth/password-reset/confirm/",
            params | {"password": "12345678"},
            format="json",
        )

        assert response.status_code == 400
        assert "password" in response.json()
        user.refresh_from_db()
        assert user.check_password(PASSWORD)


class TestEmailTasksSkipInactivePeople:
    def test_no_mail_for_inactive_people(self) -> None:
        user = make_user(is_active=False, email_verified_at=None)

        tasks.send_verification_email(user.pk)
        tasks.send_password_reset_email(user.pk)
        tasks.send_account_exists_email(user.pk)

        assert mail.outbox == []
