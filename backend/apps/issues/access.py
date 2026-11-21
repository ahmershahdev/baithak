from django.http import Http404

from apps.accounts.models import User
from apps.core import issues as rules
from apps.core.roles import Role
from apps.issues.models import Project
from apps.workspaces.access import membership
from apps.workspaces.models import Member


def projects_member(user: User, slug: str) -> Member:
    """The membership, or 404 for anyone who can't see projects (outsiders and guests)."""
    member = membership(user, slug)
    if not rules.can_view(Role(member.role)):
        raise Http404
    return member


def project_access(user: User, slug: str, key: str) -> tuple[Member, Project]:
    member = projects_member(user, slug)
    project = Project.objects.for_workspace(member.workspace).filter(key=key).first()
    if project is None:
        raise Http404
    return member, project
