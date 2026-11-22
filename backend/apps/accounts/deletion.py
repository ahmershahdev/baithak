from django.db import transaction
from django.db.models import Count, Q

from apps.accounts.models import User
from apps.chat.events import access_changed
from apps.core.roles import OnAccountDeletion, Role, on_account_deletion
from apps.files import storage
from apps.files.models import Attachment
from apps.workspaces import audit
from apps.workspaces.models import Member, Workspace


class OwnsWorkspaces(Exception):
    def __init__(self, workspaces: list[Workspace]) -> None:
        super().__init__("Hand these workspaces over first.")
        self.workspaces = workspaces


def _plan(user: User) -> dict[OnAccountDeletion, list[tuple[Workspace, Member]]]:
    plan: dict[OnAccountDeletion, list[tuple[Workspace, Member]]] = {
        o: [] for o in OnAccountDeletion
    }
    mine = Member.objects.filter(user=user).select_related("workspace").order_by("workspace_id")
    counts = {
        row["pk"]: row
        for row in Workspace.objects.filter(pk__in=mine.values("workspace_id"))
        .annotate(
            member_count=Count("members", distinct=True),
            owner_count=Count("members", filter=Q(members__role=Role.OWNER), distinct=True),
        )
        .values("pk", "member_count", "owner_count")
    }
    for member in mine:
        row = counts[member.workspace_id]
        outcome = on_account_deletion(
            Role(member.role), owners=row["owner_count"], members=row["member_count"]
        )
        plan[outcome].append((member.workspace, member))
    return plan


def blocking_workspaces(user: User) -> list[Workspace]:
    return [workspace for workspace, _ in _plan(user)[OnAccountDeletion.BLOCK]]


def delete_account(user: User) -> None:
    """Delete the person and everything only they had. Their messages, files and issues stay
    in shared workspaces with no author (the foreign keys are SET_NULL)."""
    with transaction.atomic():
        # Same lock as role changes and removals, in id order so two deletions can't deadlock.
        list(
            Workspace.objects.select_for_update()
            .filter(pk__in=Member.objects.filter(user=user).values("workspace_id"))
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        plan = _plan(user)
        if plan[OnAccountDeletion.BLOCK]:
            raise OwnsWorkspaces([w for w, _ in plan[OnAccountDeletion.BLOCK]])

        for workspace, member in plan[OnAccountDeletion.LEAVE]:
            audit.record(
                workspace,
                user,
                "member.remove",
                member,
                {"user": user.username, "reason": "account deleted"},
            )

        alone = [workspace.pk for workspace, _ in plan[OnAccountDeletion.DELETE_WORKSPACE]]
        doomed = Attachment.objects.filter(
            Q(workspace_id__in=alone) | Q(uploader=user, message=None)
        )
        keys = [key for f in doomed for key in (f.storage_key, f.preview_key) if key]
        doomed.delete()
        Workspace.objects.filter(pk__in=alone).delete()
        user_id = user.pk
        user.delete()
        # Open sockets re-check membership on this and close.
        access_changed(user_id)

        def remove_files() -> None:
            for key in keys:
                storage.delete(key)

        transaction.on_commit(remove_files)
