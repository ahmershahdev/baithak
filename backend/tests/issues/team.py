from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.issues.models import Project
from apps.workspaces.models import Workspace


def karachi_team(api: APIClient, owner: User) -> Workspace:
    """The "Karachi Team" workspace, made by `owner` (signed in after), with project BAI."""
    api.force_authenticate(owner)
    response = api.post("/api/v1/workspaces/", {"name": "Karachi Team"}, format="json")
    workspace = Workspace.objects.get(slug=response.json()["slug"])
    Project.objects.create(workspace=workspace, key="BAI", name="Baithak")
    return workspace
