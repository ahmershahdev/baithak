import itertools
from datetime import timedelta

import pytest
from django.contrib.admin.sites import AdminSite
from django.core import mail
from django.test import RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import lockout
from apps.accounts.admin import BaithakUserAdmin
from apps.accounts.models import ContactMessage, User
from tests.accounts.factories import PASSWORD, make_user

pytestmark = pytest.mark.django_db

SIGNIN = "/api/v1/auth/signin/"


_addresses = itertools.count(1)


def wrong(api: APIClient, user: User, times: int) -> list[int]:
    """Wrong passwords, each from a new IP, as a spread-out attack would come: the per-IP
    throttle never sees two, so only the account's own ladder can stop them."""
    return [
        api.post(
            SIGNIN,
            {"email": user.email, "password": "Wrong-Pass-1234"},
            format="json",
            REMOTE_ADDR=f"10.0.{next(_addresses) % 250}.{next(_addresses) % 250}",
        ).status_code
        for _ in range(times)
    ]


def expire_lock(user: User) -> None:
    User.objects.filter(pk=user.pk).update(locked_until=timezone.now() - timedelta(seconds=1))


class TestSignInLadder:
    def test_three_wrong_passwords_lock_for_an_hour_and_mail_the_owner(
        self, api: APIClient
    ) -> None:
        user = make_user()

        codes = wrong(api, user, 3)
        right = api.post(SIGNIN, {"email": user.email, "password": PASSWORD}, format="json")

        assert codes == [400, 400, 400]
        assert right.status_code == 429
        user.refresh_from_db()
        assert user.locked_until is not None
        remaining = user.locked_until - timezone.now()
        assert timedelta(minutes=59) < remaining <= timedelta(hours=1)
        assert mail.outbox[-1].to == [user.email]
        assert "locked sign-in" in str(mail.outbox[-1].body)

    def test_after_the_hour_three_more_lock_for_four_hours(self, api: APIClient) -> None:
        user = make_user()
        wrong(api, user, 3)
        expire_lock(user)

        wrong(api, user, 3)

        user.refresh_from_db()
        assert user.lock_level == 2
        assert user.locked_until is not None
        assert user.locked_until - timezone.now() > timedelta(hours=3, minutes=59)

    def test_then_a_week_then_a_ban_only_an_admin_lifts(self, api: APIClient) -> None:
        user = make_user()
        for _ in range(3):
            wrong(api, user, 3)
            expire_lock(user)
        user.refresh_from_db()
        assert user.lock_level == 3
        assert "suspended for a week" in str(mail.outbox[-1].body)

        wrong(api, user, 3)
        user.refresh_from_db()
        right = api.post(SIGNIN, {"email": user.email, "password": PASSWORD}, format="json")

        assert user.banned_at is not None
        assert right.status_code == 429
        assert "Only our support team" in str(mail.outbox[-1].body)

        admin = BaithakUserAdmin(User, AdminSite())
        request = RequestFactory().post("/admin/")
        request._messages = type("M", (), {"add": lambda *a, **k: None})()  # type: ignore[attr-defined]
        admin.unlock_accounts(request, User.objects.filter(pk=user.pk))
        unlocked = api.post(SIGNIN, {"email": user.email, "password": PASSWORD}, format="json")

        assert unlocked.status_code == 200

    def test_a_correct_password_clears_the_count(self, api: APIClient) -> None:
        user = make_user()
        wrong(api, user, 2)
        api.post(SIGNIN, {"email": user.email, "password": PASSWORD}, format="json")
        api.post("/api/v1/auth/signout/")

        user.refresh_from_db()
        assert (user.failed_attempts, user.lock_level) == (0, 0)

    def test_an_unknown_email_answers_exactly_like_a_real_one(self, api: APIClient) -> None:
        ghost = User(email="ghost@example.com")

        assert wrong(api, ghost, 4) == [400, 400, 400, 429]
        assert mail.outbox == []

    def test_the_lock_message_names_support(self, api: APIClient) -> None:
        user = make_user()
        wrong(api, user, 3)

        response = api.post(SIGNIN, {"email": user.email, "password": PASSWORD}, format="json")

        assert "support@ahmershah.dev" in response.json()["detail"]

    def test_unlock_resets_everything(self) -> None:
        user = make_user(
            failed_attempts=2, lock_level=4, banned_at=timezone.now(), locked_until=timezone.now()
        )

        lockout.unlock(user)

        user.refresh_from_db()
        assert (user.failed_attempts, user.lock_level, user.locked_until, user.banned_at) == (
            0,
            0,
            None,
            None,
        )


class TestSignUpRules:
    def body(self, **overrides: str) -> dict[str, str]:
        return {
            "email": "new@example.com",
            "username": "newcomer",
            "password": "Chai-At-Four-42",
        } | overrides

    @pytest.mark.parametrize("username", ["killj4ws", "h1tler", "admin", "mus.lim"])
    def test_blocked_and_reserved_handles_are_refused(self, api: APIClient, username: str) -> None:
        response = api.post("/api/v1/auth/signup/", self.body(username=username), format="json")

        assert response.status_code == 400
        assert "username" in response.json()
        assert User.objects.count() == 0

    def test_offensive_display_names_are_refused(self, api: APIClient) -> None:
        response = api.post(
            "/api/v1/auth/signup/", self.body(display_name="Hitler Fan"), format="json"
        )

        assert response.json() == {"display_name": ["This name is not allowed."]}

    @pytest.mark.parametrize(
        "password", ["chai-at-four-42", "CHAI-AT-FOUR-42", "Chai-At-Four-x", "ChaiAtFour42", "Ch-1"]
    )
    def test_weak_passwords_are_refused_with_what_is_missing(
        self, api: APIClient, password: str
    ) -> None:
        response = api.post("/api/v1/auth/signup/", self.body(password=password), format="json")

        assert response.status_code == 400
        assert response.json()["password"][0].startswith("Your password needs ")


class TestAvailability:
    def test_reports_taken_and_free_emails_and_handles(self, api: APIClient) -> None:
        make_user(username="amna", email="amna@example.com")

        taken = api.post(
            "/api/v1/auth/availability/",
            {"email": "Amna@Example.com", "username": "AMNA"},
            format="json",
        ).json()
        free = api.post(
            "/api/v1/auth/availability/",
            {"email": "new@example.com", "username": "newcomer"},
            format="json",
        ).json()

        assert taken["email"]["available"] is False
        assert taken["username"] == {"available": False, "message": "This handle is taken."}
        assert free == {
            "email": {"available": True, "message": ""},
            "username": {"available": True, "message": ""},
        }

    @pytest.mark.parametrize(
        ("username", "message"),
        [
            ("killj4ws", "This handle is not allowed."),
            ("support", "This handle is reserved."),
            ("a b", "Use 2 to 30 lowercase letters"),
        ],
    )
    def test_explains_handles_that_cannot_be_used(
        self, api: APIClient, username: str, message: str
    ) -> None:
        result = api.post(
            "/api/v1/auth/availability/", {"username": username}, format="json"
        ).json()

        assert result["username"]["available"] is False
        assert result["username"]["message"].startswith(message)

    def test_is_throttled(self, api: APIClient) -> None:
        codes = [
            api.post(
                "/api/v1/auth/availability/", {"username": f"u{n}x"}, format="json"
            ).status_code
            for n in range(31)
        ]

        assert codes[-1] == 429


class TestMe:
    def test_nobody_signed_in_is_204_not_an_error(self, api: APIClient) -> None:
        assert api.get("/api/v1/auth/me/").status_code == 204


class TestContact:
    def test_a_message_is_stored_and_sent_to_support_with_reply_to(
        self, api: APIClient, django_capture_on_commit_callbacks: object
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
            response = api.post(
                "/api/v1/contact/",
                {"name": "Chanda", "email": "Chanda@Example.com", "message": "Can we self-host?"},
                format="json",
            )

        assert response.status_code == 202
        sent = mail.outbox[0]
        assert sent.to == ["support@ahmershah.dev"]
        assert sent.reply_to == ["chanda@example.com"]
        assert "Can we self-host?" in str(sent.body)
        assert ContactMessage.objects.get().sent_at is not None

    def test_too_short_messages_are_refused(self, api: APIClient) -> None:
        response = api.post(
            "/api/v1/contact/",
            {"name": "A", "email": "a@example.com", "message": "hi"},
            format="json",
        )

        assert response.status_code == 400

    def test_honeypot_stores_nothing(self, api: APIClient) -> None:
        response = api.post(
            "/api/v1/contact/",
            {"name": "Bot", "email": "b@example.com", "message": "Buy now buy now", "website": "x"},
            format="json",
        )

        assert response.status_code == 202
        assert ContactMessage.objects.count() == 0
