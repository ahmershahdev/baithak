import asyncio
import datetime
from collections.abc import Iterator

import pytest
import redis
from django.conf import settings
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages, presence
from apps.chat.models import Channel, ChannelMember
from apps.core.channels import ChannelKind
from apps.core.notifications import EMAIL_AFTER
from apps.core.roles import Role
from apps.notifications.models import Notification
from apps.notifications.tasks import email_person, email_unread
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_presence() -> Iterator[None]:
    yield
    client = redis.from_url(settings.REDIS_URL)
    keys = list(client.scan_iter(f"{settings.PRESENCE_KEY_PREFIX}:*"))
    if keys:
        client.delete(*keys)
    client.close()


@pytest.fixture
def workspace(api: APIClient) -> Workspace:
    founder = make_user(username="owner")
    api.force_authenticate(founder)
    response = api.post("/api/v1/workspaces/", {"name": "Karachi Team"}, format="json")
    return Workspace.objects.get(slug=response.json()["slug"])


@pytest.fixture
def owner(workspace: Workspace) -> User:
    return Member.objects.for_workspace(workspace).get(role=Role.OWNER).user


@pytest.fixture
def general(workspace: Workspace) -> Channel:
    return Channel.objects.for_workspace(workspace).get(is_default=True)


@pytest.fixture
def bilal(workspace: Workspace, general: Channel) -> User:
    user = make_user(username="bilal", email="bilal@example.com")
    Member.objects.create(workspace=workspace, user=user, role=Role.MEMBER)
    ChannelMember.objects.create(channel=general, user=user)
    return user


def age_all(minutes: int = 15) -> None:
    Notification.objects.update(created_at=timezone.now() - datetime.timedelta(minutes=minutes))


class TestSending:
    def test_an_unread_mention_is_emailed_once(
        self, owner: User, general: Channel, bilal: User
    ) -> None:
        messages.post(general, owner, "@bilal the invoice is due today")
        age_all()

        email_unread()
        email_unread()

        assert len(mail.outbox) == 1
        sent = mail.outbox[0]
        assert sent.to == ["bilal@example.com"]
        assert (
            sent.subject == f"{owner.display_name or owner.username} mentioned you in Karachi Team"
        )
        assert "the invoice is due today" in sent.body
        assert "/w/karachi-team/notifications" in sent.body

    def test_several_go_out_as_one_email(self, owner: User, general: Channel, bilal: User) -> None:
        for text in ("@bilal one", "@bilal two", "@bilal three"):
            messages.post(general, owner, text)
        age_all()

        email_unread()

        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "3 unread messages for you in Karachi Team"

    def test_nothing_before_the_delay(self, owner: User, general: Channel, bilal: User) -> None:
        messages.post(general, owner, "@bilal quick one")
        age_all(minutes=int(EMAIL_AFTER.total_seconds() // 60) - 1)

        email_unread()

        assert mail.outbox == []

    def test_nothing_once_read(self, owner: User, general: Channel, bilal: User) -> None:
        messages.post(general, owner, "@bilal seen it?")
        Notification.objects.update(read_at=timezone.now())
        age_all()

        email_unread()

        assert mail.outbox == []

    def test_at_channel_is_not_emailed(self, owner: User, general: Channel, bilal: User) -> None:
        messages.post(general, owner, "@channel standup moved")
        age_all()

        email_unread()

        assert mail.outbox == []


class TestPreferences:
    def test_turned_off_means_no_email(self, owner: User, general: Channel, bilal: User) -> None:
        User.objects.filter(pk=bilal.pk).update(notify_by_email=False)
        messages.post(general, owner, "@bilal hello")
        age_all()

        email_unread()

        assert mail.outbox == []

    def test_quiet_hours_hold_it_until_they_end(
        self, owner: User, general: Channel, bilal: User
    ) -> None:
        now = timezone.now().astimezone(datetime.UTC)
        start = (now - datetime.timedelta(hours=1)).time()
        end = (now + datetime.timedelta(hours=1)).time()
        User.objects.filter(pk=bilal.pk).update(quiet_start=start, quiet_end=end)
        messages.post(general, owner, "@bilal late night question")
        age_all()

        email_unread()
        assert mail.outbox == []

        User.objects.filter(pk=bilal.pk).update(quiet_start=None, quiet_end=None)
        email_unread()
        assert len(mail.outbox) == 1

    def test_someone_online_in_the_workspace_gets_no_email(
        self, owner: User, workspace: Workspace, general: Channel, bilal: User
    ) -> None:
        asyncio.run(presence.connect(workspace.pk, bilal.pk, "tab-1"))
        messages.post(general, owner, "@bilal you are here")
        age_all()

        email_unread()

        assert mail.outbox == []

    def test_an_unconfirmed_email_gets_nothing(
        self, owner: User, general: Channel, bilal: User
    ) -> None:
        User.objects.filter(pk=bilal.pk).update(email_verified_at=None)
        messages.post(general, owner, "@bilal hello")
        age_all()

        email_unread()

        assert mail.outbox == []

    def test_a_channel_they_left_is_not_emailed(
        self, owner: User, workspace: Workspace, bilal: User
    ) -> None:
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE, created_by=owner
        )
        ChannelMember.objects.create(channel=secret, user=owner)
        ChannelMember.objects.create(channel=secret, user=bilal)
        messages.post(secret, owner, "@bilal secret")
        ChannelMember.objects.filter(channel=secret, user=bilal).delete()
        age_all()

        email_unread()

        assert mail.outbox == []

    def test_a_failed_send_is_given_back_for_the_retry(
        self, owner: User, general: Channel, bilal: User, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        messages.post(general, owner, "@bilal retry me")
        age_all()

        def broken(*args: object, **kwargs: object) -> None:
            raise OSError("smtp down")

        monkeypatch.setattr("apps.notifications.tasks.send_mail", broken)
        monkeypatch.setattr("apps.notifications.tasks.email_person.delay", lambda _id: None)

        with pytest.raises(OSError, match="smtp down"):
            email_person.run(bilal.pk)

        assert Notification.objects.get().emailed_at is None


class TestSettingsApi:
    URL = "/api/v1/auth/notifications/"

    def test_read_and_change(self, api: APIClient, bilal: User) -> None:
        api.force_authenticate(bilal)

        start = api.get(self.URL).json()
        changed = api.patch(
            self.URL,
            {"quiet_start": "22:00", "quiet_end": "07:00", "time_zone": "Asia/Karachi"},
            format="json",
        )

        assert start == {
            "notify_by_email": True,
            "quiet_start": None,
            "quiet_end": None,
            "time_zone": "UTC",
        }
        assert changed.status_code == 200
        assert changed.json()["quiet_start"] == "22:00:00"
        assert changed.json()["time_zone"] == "Asia/Karachi"

    def test_half_quiet_hours_or_a_made_up_zone_are_refused(
        self, api: APIClient, bilal: User
    ) -> None:
        api.force_authenticate(bilal)

        half = api.patch(self.URL, {"quiet_start": "22:00"}, format="json")
        zone = api.patch(self.URL, {"time_zone": "Mars/Olympus"}, format="json")

        assert (half.status_code, zone.status_code) == (400, 400)

    def test_signed_out_is_refused(self, api: APIClient, workspace: Workspace) -> None:
        api.force_authenticate(None)

        assert api.get(self.URL).status_code == 403
