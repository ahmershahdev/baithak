from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import devices
from apps.accounts.models import Device, User
from tests.accounts.factories import PASSWORD, make_user

pytestmark = pytest.mark.django_db

AUTH = "/api/v1/auth/"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0"
CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


@pytest.fixture
def amna() -> User:
    return make_user(username="amna")


def device(user: User, agent: str = FIREFOX) -> APIClient:
    """A browser that signed in for real, so it has a session and a device row."""
    client = APIClient(HTTP_USER_AGENT=agent)
    response = client.post(
        f"{AUTH}signin/", {"email": user.email, "password": PASSWORD}, format="json"
    )
    assert response.status_code == 200
    return client


def signed_in(client: APIClient) -> bool:
    return client.get(f"{AUTH}me/").status_code == 200


def device_id(client: APIClient) -> Any:
    return client.session[devices.SESSION_KEY]


class TestListing:
    def test_each_sign_in_is_a_device_named_by_its_browser(self, amna: User) -> None:
        laptop = device(amna, CHROME)
        device(amna, FIREFOX)

        listed = laptop.get(f"{AUTH}devices/").json()

        assert {(d["name"], d["current"]) for d in listed} == {
            ("Chrome on Windows", True),
            ("Firefox on Linux", False),
        }

    def test_signing_out_removes_the_device(self, amna: User) -> None:
        laptop = device(amna)

        laptop.post(f"{AUTH}signout/")

        assert not Device.objects.filter(user=amna).exists()

    def test_someone_elses_devices_are_not_listed_or_touched(self, amna: User) -> None:
        bilal = make_user(username="bilal")
        theirs = device(bilal)
        mine = device(amna)

        listed = mine.get(f"{AUTH}devices/").json()
        refused = mine.delete(f"{AUTH}devices/{device_id(theirs)}/")

        assert [d["id"] for d in listed] == [device_id(mine)]
        assert refused.status_code == 404
        assert signed_in(theirs)

    def test_signed_out_people_get_nothing(self, api: APIClient) -> None:
        assert api.get(f"{AUTH}devices/").status_code == 403
        assert api.post(f"{AUTH}devices/sign-out-others/").status_code == 403


class TestSigningOut:
    def test_one_device_is_signed_out_on_its_next_request(self, amna: User) -> None:
        laptop = device(amna, CHROME)
        phone = device(amna, FIREFOX)

        response = laptop.delete(f"{AUTH}devices/{device_id(phone)}/")

        assert response.status_code == 204
        assert not signed_in(phone)
        assert signed_in(laptop)

    def test_every_other_device(self, amna: User) -> None:
        laptop = device(amna)
        others = [device(amna), device(amna)]

        response = laptop.post(f"{AUTH}devices/sign-out-others/")

        assert response.json() == {"signed_out": 2}
        assert [signed_in(other) for other in others] == [False, False]
        assert signed_in(laptop)

    def test_deactivating_an_account_signs_out_everywhere(self, amna: User) -> None:
        laptop, phone = device(amna), device(amna)

        amna.is_active = False
        with TestCase.captureOnCommitCallbacks(execute=True):
            amna.save()

        assert not Device.objects.filter(user=amna).exists()
        assert not signed_in(laptop)
        assert not signed_in(phone)

    def test_a_password_reset_signs_out_everywhere(self, amna: User) -> None:
        laptop = device(amna)
        stranger = APIClient()
        stranger.post(f"{AUTH}password-reset/", {"email": amna.email}, format="json")
        code = next(w for w in str(mail.outbox[-1].subject).split() if w.isdigit())

        stranger.post(
            f"{AUTH}password-reset/confirm/",
            {"email": amna.email, "code": code, "password": "A-new-chai-At-Five-77"},
            format="json",
        )

        assert not Device.objects.filter(user=amna).exists()
        assert not signed_in(laptop)


class TestKeepingTrack:
    def test_a_session_from_before_devices_gets_one(self, amna: User) -> None:
        laptop = device(amna)
        Device.objects.filter(user=amna).delete()
        session = laptop.session
        del session[devices.SESSION_KEY]
        session.save()

        assert signed_in(laptop)
        assert Device.objects.filter(user=amna).count() == 1

    def test_last_seen_moves_at_most_every_five_minutes(
        self, amna: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        laptop = device(amna)
        first = Device.objects.get(user=amna).last_seen_at
        signed_in(laptop)
        assert Device.objects.get(user=amna).last_seen_at == first

        later = timezone.now() + devices.SEEN_EVERY + timedelta(seconds=1)
        monkeypatch.setattr("apps.accounts.devices.timezone.now", lambda: later)
        signed_in(laptop)

        assert Device.objects.get(user=amna).last_seen_at == later

    def test_devices_whose_session_ran_out_are_pruned(self, amna: User) -> None:
        device(amna)
        stale = Device.objects.create(
            user=amna,
            last_seen_at=timezone.now() - timedelta(seconds=settings.SESSION_COOKIE_AGE + 60),
        )

        assert devices.prune() == 1
        assert not Device.objects.filter(pk=stale.pk).exists()
        assert Device.objects.filter(user=amna).count() == 1
