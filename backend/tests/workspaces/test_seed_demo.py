from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import User
from apps.chat.models import Channel, ChannelMember, Message
from apps.issues.models import Issue
from apps.notifications.models import Notification
from apps.workspaces.models import Member, Workspace

pytestmark = pytest.mark.django_db


def seed(*extra: str) -> str:
    out = StringIO()
    call_command(
        "seed_demo", "--days", "4", "--password", "a long demo password", *extra, stdout=out
    )
    return out.getvalue()


def test_seeding_makes_two_lived_in_teams() -> None:
    """One seed, checked from several sides: seeding takes a while even for a few days."""
    seed()

    teams = Workspace.objects.order_by("slug")
    assert [t.slug for t in teams] == ["chai-and-code", "monsoon-press"]
    for team in teams:
        assert Channel.objects.for_workspace(team).filter(is_default=True).count() == 1
        assert Issue.objects.for_workspace(team).count() >= 10
        assert Issue.objects.for_workspace(team).filter(message__isnull=False).exists()

    dev = Channel.objects.get(name="dev")
    times = list(
        Message.objects.filter(channel=dev, seq__isnull=False)
        .order_by("seq")
        .values_list("created_at", flat=True)
    )
    assert times == sorted(times)

    amna = User.objects.get(username="amna")
    assert amna.email == "amna@chai-and-code.example"
    assert amna.check_password("a long demo password")
    assert not User.objects.filter(email__endswith=".example", notify_by_email=True).exists()
    assert mail.outbox == []

    daniel = User.objects.get(username="daniel")
    rooms = ChannelMember.objects.filter(user=daniel).values_list("channel__name", flat=True)
    assert list(rooms) == ["client-bazaar"]
    assert Member.objects.get(user=daniel).role == "guest"

    marker = ChannelMember.objects.get(channel=dev, user=amna).last_read_seq
    assert marker < dev.last_seq
    assert not Notification.objects.filter(
        read_at__isnull=True, created_at__lt=dev.created_at
    ).exists()


def test_running_twice_refuses_and_reset_replaces() -> None:
    seed()

    with pytest.raises(CommandError, match="Already there"):
        seed()

    out = seed("--reset")
    assert "Seeded /w/chai-and-code" in out
    assert Workspace.objects.count() == 2


def test_a_taken_handle_is_reported() -> None:
    User.objects.create_user(username="bilal", email="bilal@elsewhere.example", password="x")

    with pytest.raises(CommandError, match="@bilal"):
        seed()
