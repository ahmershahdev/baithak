from typing import Any
from urllib.parse import quote

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember, Message, Reaction
from apps.core.reactions import MAX_DISTINCT
from apps.core.roles import Role
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/workspaces/karachi-team/channels/"
# Escapes, not emoji characters, per AGENTS.md.
THUMBS_UP = "\U0001f44d"
HEART = "❤️"
# Regional indicators: each pair is a flag, so there are plenty of distinct emoji to use.
FLAGS = [chr(0x1F1E6 + i) + chr(0x1F1E6 + j) for i in range(5) for j in range(5)]


@pytest.fixture
def owner() -> User:
    return make_user(username="owner")


@pytest.fixture
def workspace(api: APIClient, owner: User) -> Workspace:
    api.force_authenticate(owner)
    response = api.post("/api/v1/workspaces/", {"name": "Karachi Team"}, format="json")
    return Workspace.objects.get(slug=response.json()["slug"])


@pytest.fixture
def general(workspace: Workspace) -> Channel:
    return Channel.objects.for_workspace(workspace).get(name="general")


@pytest.fixture
def bilal(workspace: Workspace, general: Channel) -> User:
    user = make_user(username="bilal")
    Member.objects.create(workspace=workspace, user=user, role=Role.MEMBER)
    ChannelMember.objects.create(channel=general, user=user)
    return user


@pytest.fixture
def first(general: Channel, bilal: User) -> Message:
    message, _ = messages.post(general, bilal, "Chai at four?")
    return message


def add(api: APIClient, channel: Channel, emoji: str, path: str = "messages/1/") -> Any:
    return api.post(f"{BASE}{channel.pk}/{path}reactions/", {"emoji": emoji}, format="json")


def remove(api: APIClient, channel: Channel, emoji: str, path: str = "messages/1/") -> Any:
    return api.delete(f"{BASE}{channel.pk}/{path}reactions/{quote(emoji)}/")


class TestReacting:
    def test_reactions_are_grouped_by_emoji_with_who_reacted(
        self, api: APIClient, general: Channel, first: Message, bilal: User
    ) -> None:
        add(api, general, THUMBS_UP)
        api.force_authenticate(bilal)
        add(api, general, HEART)
        response = add(api, general, THUMBS_UP)

        body = response.json()
        assert [(r["emoji"], r["count"]) for r in body["reactions"]] == [
            (THUMBS_UP, 2),
            (HEART, 1),
        ]
        assert [u["username"] for u in body["reactions"][0]["users"]] == ["owner", "bilal"]

    def test_reacting_twice_is_stored_once(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        add(api, general, THUMBS_UP)
        add(api, general, THUMBS_UP)

        assert Reaction.objects.filter(message=first).count() == 1

    def test_a_reaction_gives_the_message_a_new_event(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        add(api, general, THUMBS_UP)

        page = api.get(f"{BASE}{general.pk}/messages/", {"after_event": 1}).json()
        assert [(m["seq"], m["event"]) for m in page["messages"]] == [(1, 2)]
        assert page["messages"][0]["reactions"][0]["emoji"] == THUMBS_UP

    def test_taking_it_back(self, api: APIClient, general: Channel, first: Message) -> None:
        add(api, general, THUMBS_UP)

        response = remove(api, general, THUMBS_UP)

        assert response.status_code == 200
        assert response.json()["reactions"] == []
        first.refresh_from_db()
        assert first.event == 3

    def test_taking_back_what_is_not_there_changes_nothing(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        remove(api, general, THUMBS_UP)

        first.refresh_from_db()
        assert first.event == 1

    @pytest.mark.parametrize("emoji", ["ok", "", "<script>", THUMBS_UP + " nice"])
    def test_only_one_emoji_is_accepted(
        self, api: APIClient, general: Channel, first: Message, emoji: str
    ) -> None:
        assert add(api, general, emoji).status_code == 400

    def test_a_message_holds_a_limited_number_of_different_emoji(
        self, api: APIClient, general: Channel, first: Message, bilal: User
    ) -> None:
        for flag in FLAGS[:MAX_DISTINCT]:
            add(api, general, flag)

        refused = add(api, general, FLAGS[MAX_DISTINCT])
        api.force_authenticate(bilal)
        joined = add(api, general, FLAGS[0])

        assert refused.status_code == 400
        assert joined.status_code == 200

    def test_replies_take_reactions(
        self, api: APIClient, general: Channel, first: Message, bilal: User
    ) -> None:
        messages.post(general, bilal, "Yes", parent=first)

        response = add(api, general, THUMBS_UP, "messages/1/replies/1/")

        assert response.json()["thread_seq"] == 1
        assert response.json()["reactions"][0]["count"] == 1


class TestWhoMayReact:
    def test_someone_outside_the_channel_may_not(
        self, api: APIClient, workspace: Workspace, general: Channel, first: Message
    ) -> None:
        reader = make_user(username="reader")
        Member.objects.create(workspace=workspace, user=reader, role=Role.MEMBER)
        api.force_authenticate(reader)

        assert add(api, general, THUMBS_UP).status_code == 403

    def test_not_in_an_archived_channel(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        Channel.objects.filter(pk=general.pk).update(archived_at=timezone.now())

        assert add(api, general, THUMBS_UP).status_code == 403

    def test_deleting_a_message_removes_its_reactions(
        self, api: APIClient, general: Channel, first: Message
    ) -> None:
        add(api, general, THUMBS_UP)

        messages.delete(first)

        assert not Reaction.objects.filter(message=first).exists()
        assert add(api, general, HEART).status_code == 403
