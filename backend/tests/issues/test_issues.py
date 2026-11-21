import threading
from typing import Any

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.roles import Role
from apps.issues.models import Issue, Label, Project
from apps.issues.services import create_issue
from apps.workspaces.models import AuditEvent, Member, Workspace
from tests.accounts.factories import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/workspaces/karachi-team/projects/"


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
def project(api: APIClient, workspace: Workspace) -> Project:
    response = api.post(BASE, {"key": "bai", "name": "Baithak"}, format="json")
    assert response.status_code == 201, response.json()
    return Project.objects.for_workspace(workspace).get(key="BAI")


def join(workspace: Workspace, username: str, role: Role = Role.MEMBER) -> User:
    user = make_user(username=username)
    Member.objects.create(workspace=workspace, user=user, role=role)
    return user


def open_issue(api: APIClient, **body: Any) -> Any:
    response = api.post(f"{BASE}BAI/issues/", {"title": "Something", **body}, format="json")
    assert response.status_code == 201, response.json()
    return response.json()


class TestProjects:
    def test_a_project_key_is_upper_case_and_unique(self, api: APIClient, project: Project) -> None:
        again = api.post(BASE, {"key": "BAI", "name": "Again"}, format="json")
        bad = api.post(BASE, {"key": "2x", "name": "Bad"}, format="json")

        assert project.key == "BAI"
        assert (again.status_code, bad.status_code) == (400, 400)

    def test_only_admins_create_and_change_projects(
        self, api: APIClient, workspace: Workspace, project: Project
    ) -> None:
        api.force_authenticate(join(workspace, "bilal"))

        made = api.post(BASE, {"key": "OPS", "name": "Ops"}, format="json")
        renamed = api.patch(f"{BASE}BAI/", {"name": "Mine"}, format="json")

        assert (made.status_code, renamed.status_code) == (403, 403)

    def test_guests_cannot_see_projects_at_all(
        self, api: APIClient, workspace: Workspace, project: Project
    ) -> None:
        api.force_authenticate(join(workspace, "guest", Role.GUEST))

        assert api.get(BASE).status_code == 404
        assert api.get(f"{BASE}BAI/issues/").status_code == 404

    def test_the_list_counts_open_issues(self, api: APIClient, project: Project) -> None:
        open_issue(api)
        open_issue(api, status="done")

        listed = api.get(BASE).json()

        assert [(p["key"], p["open_issues"]) for p in listed] == [("BAI", 1)]

    def test_an_archived_project_is_read_only(self, api: APIClient, project: Project) -> None:
        api.patch(f"{BASE}BAI/", {"archived": True}, format="json")

        response = api.post(f"{BASE}BAI/issues/", {"title": "Late"}, format="json")

        assert response.status_code == 403
        assert api.get(f"{BASE}BAI/issues/").status_code == 200


class TestNumbers:
    def test_issues_are_numbered_from_one_per_project(
        self, api: APIClient, project: Project
    ) -> None:
        first, second = open_issue(api), open_issue(api)
        api.post(BASE, {"key": "OPS", "name": "Ops"}, format="json")
        other = api.post(f"{BASE}OPS/issues/", {"title": "Elsewhere"}, format="json").json()

        assert (first["ref"], second["ref"], other["ref"]) == ("BAI-1", "BAI-2", "OPS-1")

    def test_a_refused_issue_takes_no_number(self, api: APIClient, project: Project) -> None:
        open_issue(api)
        api.post(f"{BASE}BAI/issues/", {"title": "x", "assignee_id": 999_999}, format="json")

        assert open_issue(api)["number"] == 2


@pytest.mark.django_db(transaction=True)
def test_concurrent_creates_get_distinct_gap_free_numbers() -> None:
    """Numbered under a lock on the project row: parallel creators never share or skip one."""
    author = make_user(username="author")
    workspace = Workspace.objects.create(name="Race", slug="race", created_by=author)
    project = Project.objects.create(workspace=workspace, key="RACE", name="Race")
    errors: list[Exception] = []

    def worker(n: int) -> None:
        try:
            for i in range(5):
                create_issue(project, author, {"title": f"{n}-{i}"})
        # Any failure in a thread would otherwise vanish; collect it for the assert below.
        except Exception as error:
            errors.append(error)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    numbers = sorted(Issue.objects.filter(project=project).values_list("number", flat=True))
    assert numbers == list(range(1, 21))
    project.refresh_from_db()
    assert project.next_number == 21


class TestEditing:
    def test_assign_label_schedule_and_close(
        self, api: APIClient, workspace: Workspace, project: Project
    ) -> None:
        bilal = join(workspace, "bilal")
        bug = api.post(f"{BASE}BAI/labels/", {"name": "bug", "color": "danger"}, format="json")
        issue = open_issue(api)

        changed = api.patch(
            f"{BASE}BAI/issues/1/",
            {
                "assignee_id": bilal.pk,
                "label_ids": [bug.json()["id"]],
                "priority": "high",
                "due": "2026-12-01",
                "status": "done",
            },
            format="json",
        ).json()

        assert issue["closed_at"] is None
        assert changed["assignee"]["username"] == "bilal"
        assert [label["name"] for label in changed["labels"]] == ["bug"]
        assert (changed["priority"], changed["due"]) == ("high", "2026-12-01")
        assert changed["closed_at"] is not None

    def test_reopening_clears_closed_at(self, api: APIClient, project: Project) -> None:
        open_issue(api, status="done")

        reopened = api.patch(f"{BASE}BAI/issues/1/", {"status": "todo"}, format="json").json()

        assert reopened["closed_at"] is None

    def test_guests_and_strangers_cannot_be_assigned(
        self, api: APIClient, workspace: Workspace, project: Project
    ) -> None:
        guest = join(workspace, "guest", Role.GUEST)
        stranger = make_user(username="stranger")
        open_issue(api)

        for person in (guest, stranger):
            response = api.patch(f"{BASE}BAI/issues/1/", {"assignee_id": person.pk}, format="json")
            assert response.status_code == 400

    def test_labels_from_another_project_are_refused(
        self, api: APIClient, workspace: Workspace, project: Project
    ) -> None:
        api.post(BASE, {"key": "OPS", "name": "Ops"}, format="json")
        theirs = api.post(f"{BASE}OPS/labels/", {"name": "infra", "color": "info"}, format="json")
        open_issue(api)

        response = api.patch(
            f"{BASE}BAI/issues/1/", {"label_ids": [theirs.json()["id"]]}, format="json"
        )

        assert response.status_code == 400

    def test_changes_are_audited_without_the_description_text(
        self, api: APIClient, workspace: Workspace, project: Project
    ) -> None:
        open_issue(api, description="secret plan")

        api.patch(
            f"{BASE}BAI/issues/1/",
            {"title": "Better title", "description": "new secret plan"},
            format="json",
        )

        event = AuditEvent.objects.for_workspace(workspace).order_by("-id").first()
        assert event is not None
        assert event.action == "issue.update"
        assert event.changes == {
            "issue": "BAI-1",
            "title": ["Something", "Better title"],
            "description": ["(changed)", "(changed)"],
        }

    def test_deleting_a_label_takes_it_off_issues(self, api: APIClient, project: Project) -> None:
        bug = api.post(f"{BASE}BAI/labels/", {"name": "bug", "color": "danger"}, format="json")
        open_issue(api, label_ids=[bug.json()["id"]])

        api.delete(f"{BASE}BAI/labels/{bug.json()['id']}/")

        assert api.get(f"{BASE}BAI/issues/1/").json()["labels"] == []
        assert not Label.objects.filter(project=project).exists()


class TestListing:
    def test_filters(self, api: APIClient, workspace: Workspace, project: Project) -> None:
        bilal = join(workspace, "bilal")
        bug = api.post(f"{BASE}BAI/labels/", {"name": "bug", "color": "danger"}, format="json")
        open_issue(api, title="mine", assignee_id=bilal.pk)
        open_issue(api, title="labelled", label_ids=[bug.json()["id"]], priority="urgent")
        open_issue(api, title="finished", status="done")

        def titles(**params: Any) -> list[str]:
            found = api.get(f"{BASE}BAI/issues/", params).json()["results"]
            return [issue["title"] for issue in found]

        assert titles() == ["finished", "labelled", "mine"]
        assert titles(open="true") == ["labelled", "mine"]
        assert titles(open="false") == ["finished"]
        assert titles(assignee="@bilal") == ["mine"]
        assert titles(assignee="none") == ["finished", "labelled"]
        assert titles(label=bug.json()["id"]) == ["labelled"]
        assert titles(priority="urgent") == ["labelled"]
        assert titles(status="done,canceled") == ["finished"]

    def test_pages_go_back_by_number(self, api: APIClient, project: Project) -> None:
        for number in range(53):
            open_issue(api, title=f"issue {number + 1}")

        first = api.get(f"{BASE}BAI/issues/").json()
        second = api.get(f"{BASE}BAI/issues/", {"before": first["next"]}).json()

        assert len(first["results"]) == 50
        assert [i["number"] for i in second["results"]] == [3, 2, 1]
        assert second["next"] is None


class TestBoard:
    def test_a_column_puts_the_most_pressing_first_and_counts_them_all(
        self, api: APIClient, project: Project
    ) -> None:
        open_issue(api, title="low", priority="low")
        open_issue(api, title="urgent", priority="urgent")
        open_issue(api, title="none")
        open_issue(api, title="high", priority="high")
        open_issue(api, title="also urgent", priority="urgent")
        open_issue(api, title="done", priority="urgent", status="done")

        column = api.get(f"{BASE}BAI/issues/", {"status": "todo", "order": "priority"}).json()

        assert [i["title"] for i in column["results"]] == [
            "also urgent",
            "urgent",
            "high",
            "low",
            "none",
        ]
        assert (column["total"], column["next"]) == (5, None)

    def test_a_long_column_shows_the_first_hundred_and_the_total(
        self, project: Project, owner: User, api: APIClient
    ) -> None:
        for number in range(103):
            create_issue(project, owner, {"title": f"issue {number}"})

        column = api.get(f"{BASE}BAI/issues/", {"order": "priority"}).json()

        assert (len(column["results"]), column["total"]) == (100, 103)
