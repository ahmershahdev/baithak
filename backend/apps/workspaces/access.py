from django.http import Http404

from apps.accounts.models import User
from apps.core.roles import Role
from apps.workspaces.models import Member


def membership(user: User, slug: str) -> Member:
    """The person's membership in the workspace, or 404.

    A workspace the person is not in answers exactly like one that doesn't exist, so slugs
    can't be probed (AGENTS.md: can't see means 404, never 403).
    """
    member = (
        Member.objects.select_related("workspace").filter(workspace__slug=slug, user=user).first()
    )
    if member is None:
        raise Http404
    return member


def role_of(member: Member) -> Role:
    return Role(member.role)
