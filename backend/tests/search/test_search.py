import datetime
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.chat import messages
from apps.chat.models import Channel, ChannelMember, Message
from apps.chat.services import create_default_channel
from apps.core.channels import ChannelKind
from apps.core.roles import Role
from apps.files import storage
from apps.files.models import Attachment, Scan
from apps.issues.models import Project
from apps.issues.services import create_issue
from apps.search.queries import PAGE_SIZE
from apps.workspaces.models import Member, Workspace
from tests.accounts.factories import make_user

# InnoDB adds rows to a FULLTEXT index only when they commit, so these tests really commit.
pytestmark = pytest.mark.django_db(transaction=True)

URL = "/api/v1/workspaces/team/search/"


@pytest.fixture
def workspace() -> Workspace:
    """A team with its owner and #general."""
    founder = make_user(username="owner")
    team = Workspace.objects.create(name="Team", slug="team", created_by=founder)
    Member.objects.create(workspace=team, user=founder, role=Role.OWNER)
    create_default_channel(team, founder)
    return team


@pytest.fixture
def owner(workspace: Workspace) -> User:
    return Member.objects.for_workspace(workspace).get(role=Role.OWNER).user


@pytest.fixture
def general(workspace: Workspace) -> Channel:
    return Channel.objects.for_workspace(workspace).get(is_default=True)


@pytest.fixture
def signed_in(api: APIClient, owner: User) -> APIClient:
    api.force_authenticate(owner)
    return api


def join(workspace: Workspace, username: str, role: Role = Role.MEMBER) -> User:
    user = make_user(username=username)
    Member.objects.create(workspace=workspace, user=user, role=role)
    return user


def find(api: APIClient, kind: str = "messages", **params: Any) -> Any:
    response = api.get(f"{URL}{kind}/", params)
    assert response.status_code == 200, response.json()
    return response.json()


def bodies(found: Any) -> list[str]:
    return [hit["message"]["body"] for hit in found["results"]]


class TestFinding:
    def test_every_word_must_match_and_words_match_as_prefixes(
        self, signed_in: APIClient, owner: User, general: Channel
    ) -> None:
        messages.post(general, owner, "Deployment is done for the release")
        messages.post(general, owner, "Deployment failed again")
        messages.post(general, owner, "Lunch at four")

        found = find(signed_in, q="deploy release")

        assert found["terms"] == ["deploy", "release"]
        assert bodies(found) == ["Deployment is done for the release"]
        assert found["results"][0]["channel"] == general.pk

    def test_newest_first_with_a_next_page(
        self, signed_in: APIClient, owner: User, general: Channel
    ) -> None:
        for number in range(PAGE_SIZE + 3):
            messages.post(general, owner, f"standup note {number}")

        first = find(signed_in, q="standup")
        second = find(signed_in, q="standup", before_id=first["next"])

        assert bodies(first)[0] == f"standup note {PAGE_SIZE + 2}"
        assert len(first["results"]) == PAGE_SIZE
        assert bodies(second) == ["standup note 2", "standup note 1", "standup note 0"]
        assert second["next"] is None

    def test_only_short_or_common_words_find_nothing(
        self, signed_in: APIClient, owner: User, general: Channel
    ) -> None:
        messages.post(general, owner, "it is on the way")

        assert find(signed_in, q="it is on the") == {"terms": [], "results": [], "next": None}

    def test_deleted_messages_are_not_found(
        self, signed_in: APIClient, owner: User, general: Channel
    ) -> None:
        message, _ = messages.post(general, owner, "password for the staging box")
        messages.delete(message)

        assert bodies(find(signed_in, q="password")) == []

    def test_thread_replies_are_found_with_their_thread(
        self, signed_in: APIClient, owner: User, general: Channel
    ) -> None:
        first, _ = messages.post(general, owner, "Who has the invoice?")
        messages.post(general, owner, "The invoice is in the drive", parent=first)

        found = find(signed_in, q="drive")

        assert found["results"][0]["message"]["parent_seq"] == first.seq


class TestFilters:
    def test_by_channel_person_and_day(
        self, signed_in: APIClient, owner: User, workspace: Workspace, general: Channel
    ) -> None:
        bilal = join(workspace, "bilal")
        ChannelMember.objects.create(channel=general, user=bilal)
        random = Channel.objects.create(
            workspace=workspace, name="random", kind=ChannelKind.PUBLIC, created_by=owner
        )
        ChannelMember.objects.create(channel=random, user=owner)
        messages.post(general, owner, "budget draft from owner")
        messages.post(general, bilal, "budget draft from bilal")
        old, _ = messages.post(random, owner, "budget draft in random")
        Message.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=30)
        )

        in_random = find(signed_in, q="budget", channel=random.pk)
        by_bilal = find(signed_in, q="budget", author="@Bilal")
        recent = find(signed_in, q="budget", after=timezone.now().date().isoformat())

        assert bodies(in_random) == ["budget draft in random"]
        assert bodies(by_bilal) == ["budget draft from bilal"]
        assert "budget draft in random" not in bodies(recent)
        assert len(bodies(recent)) == 2

    def test_a_day_range_backwards_is_refused(self, signed_in: APIClient, general: Channel) -> None:
        response = signed_in.get(
            f"{URL}messages/", {"q": "budget", "after": "2026-11-20", "before": "2026-11-01"}
        )

        assert response.status_code == 400


class TestPrivacy:
    def test_private_channels_and_conversations_stay_private(
        self, api: APIClient, owner: User, workspace: Workspace, general: Channel
    ) -> None:
        bilal = join(workspace, "bilal")
        admin = join(workspace, "admin", Role.ADMIN)
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE, created_by=owner
        )
        ChannelMember.objects.create(channel=secret, user=owner)
        direct = Channel.objects.create(
            workspace=workspace, name="~1-2", kind=ChannelKind.DIRECT, created_by=owner
        )
        ChannelMember.objects.create(channel=direct, user=owner)
        ChannelMember.objects.create(channel=direct, user=bilal)
        messages.post(general, owner, "salary review is public news")
        messages.post(secret, owner, "salary review numbers")
        messages.post(direct, owner, "salary review for you")

        api.force_authenticate(admin)
        seen_by_admin = bodies(find(api, q="salary"))
        api.force_authenticate(bilal)
        seen_by_bilal = bodies(find(api, q="salary"))
        asking_for_secret = bodies(find(api, q="salary", channel=secret.pk))

        assert seen_by_admin == ["salary review is public news"]
        assert seen_by_bilal == ["salary review for you", "salary review is public news"]
        assert asking_for_secret == []

    def test_a_guest_finds_only_their_channels(
        self, api: APIClient, owner: User, workspace: Workspace, general: Channel
    ) -> None:
        guest = join(workspace, "guest", Role.GUEST)
        messages.post(general, owner, "roadmap for next quarter")
        api.force_authenticate(guest)

        assert bodies(find(api, q="roadmap")) == []


class TestFiles:
    def _attach(
        self, channel: Channel, author: User, name: str, scan: Scan = Scan.CLEAN
    ) -> Attachment:
        attachment = Attachment.objects.create(
            workspace=channel.workspace,
            channel=channel,
            uploader=author,
            name=name,
            content_type="application/pdf",
            size=10,
            storage_key=storage.new_key(),
            scan=scan,
        )
        messages.post(channel, author, "", attachment_ids=[attachment.pk])
        return attachment

    def test_files_are_found_by_name(
        self, signed_in: APIClient, owner: User, general: Channel
    ) -> None:
        self._attach(general, owner, "quarterly-report-2026.pdf")
        self._attach(general, owner, "lunch-menu.pdf")

        found = find(signed_in, "files", q="quarterly")

        assert [hit["file"]["name"] for hit in found["results"]] == ["quarterly-report-2026.pdf"]
        assert found["results"][0]["message_seq"] == 1

    def test_files_being_checked_or_refused_are_not_found(
        self, signed_in: APIClient, owner: User, general: Channel
    ) -> None:
        self._attach(general, owner, "contract-pending.pdf", Scan.PENDING)
        # Sent while still being checked, then refused by the scan.
        infected = self._attach(general, owner, "contract-infected.pdf", Scan.PENDING)
        Attachment.objects.filter(pk=infected.pk).update(scan=Scan.INFECTED)
        self._attach(general, owner, "contract-signed.pdf")

        found = find(signed_in, "files", q="contract")

        assert [hit["file"]["name"] for hit in found["results"]] == ["contract-signed.pdf"]

    def test_unsent_files_are_not_found(
        self, signed_in: APIClient, owner: User, general: Channel
    ) -> None:
        Attachment.objects.create(
            workspace=general.workspace,
            channel=general,
            uploader=owner,
            name="draft-contract.pdf",
            content_type="application/pdf",
            size=10,
            storage_key=storage.new_key(),
        )

        assert find(signed_in, "files", q="contract")["results"] == []


class TestIssues:
    @pytest.fixture
    def project(self, workspace: Workspace) -> Project:
        return Project.objects.create(workspace=workspace, key="BAI", name="Baithak")

    def refs(self, found: Any) -> list[str]:
        return [hit["ref"] for hit in found["results"]]

    def test_title_and_description_match_newest_first(
        self, signed_in: APIClient, owner: User, project: Project
    ) -> None:
        create_issue(project, owner, {"title": "Uploads fail on Safari"})
        create_issue(project, owner, {"title": "Crash", "description": "Only when uploading"})
        create_issue(project, owner, {"title": "Unrelated"})

        found = find(signed_in, "issues", q="upload")

        assert self.refs(found) == ["BAI-2", "BAI-1"]
        assert found["results"][1]["status"] == "todo"

    def test_filters_by_who_opened_it_and_the_channel_it_came_from(
        self,
        signed_in: APIClient,
        workspace: Workspace,
        owner: User,
        general: Channel,
        project: Project,
    ) -> None:
        bilal = join(workspace, "bilal")
        source, _ = messages.post(general, owner, "Uploads are broken")
        create_issue(project, owner, {"title": "Uploads from chat", "message": source})
        create_issue(project, bilal, {"title": "Uploads by Bilal"})

        assert self.refs(find(signed_in, "issues", q="uploads", author="@bilal")) == ["BAI-2"]
        assert self.refs(find(signed_in, "issues", q="uploads", channel=general.pk)) == ["BAI-1"]

    def test_a_channel_you_cannot_read_finds_nothing(
        self, api: APIClient, workspace: Workspace, owner: User, project: Project
    ) -> None:
        secret = Channel.objects.create(
            workspace=workspace, name="secret", kind=ChannelKind.PRIVATE
        )
        ChannelMember.objects.create(channel=secret, user=owner)
        source, _ = messages.post(secret, owner, "Salaries")
        create_issue(project, owner, {"title": "Salaries sheet", "message": source})
        api.force_authenticate(join(workspace, "bilal"))

        assert self.refs(find(api, "issues", q="salaries")) == ["BAI-1"]
        assert self.refs(find(api, "issues", q="salaries", channel=secret.pk)) == []

    def test_guests_cannot_search_issues(
        self, api: APIClient, workspace: Workspace, owner: User, project: Project
    ) -> None:
        create_issue(project, owner, {"title": "Uploads fail"})
        api.force_authenticate(join(workspace, "guest", Role.GUEST))

        assert api.get(f"{URL}issues/", {"q": "uploads"}).status_code == 404

    def test_another_workspace_s_issues_are_never_found(
        self, signed_in: APIClient, owner: User, project: Project
    ) -> None:
        other = Workspace.objects.create(name="Other", slug="other", created_by=owner)
        elsewhere = Project.objects.create(workspace=other, key="OTH", name="Other")
        create_issue(elsewhere, owner, {"title": "Uploads elsewhere"})

        assert self.refs(find(signed_in, "issues", q="uploads")) == []
