from typing import Any

from django.db import models

from apps.accounts.models import User
from apps.workspaces.models import AuditEvent, Workspace


def record(
    workspace: Workspace,
    actor: User | None,
    action: str,
    obj: models.Model,
    changes: dict[str, Any] | None = None,
) -> AuditEvent:
    """Write one audit row. Call inside the same transaction as the change it describes."""
    return AuditEvent.objects.create(
        workspace=workspace,
        actor=actor,
        action=action,
        model=obj._meta.model_name or "",
        object_id=str(obj.pk),
        changes=changes or {},
    )


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    """{field: [old, new]} for the fields that changed."""
    return {key: [before[key], after[key]] for key in after if before.get(key) != after[key]}
