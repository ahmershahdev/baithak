from functools import partial
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.files import storage
from apps.files.models import Attachment


def _delete_all(keys: tuple[str, ...]) -> None:
    for key in keys:
        storage.delete(key)


class Command(BaseCommand):
    help = "Encrypt files stored before encryption at rest. Safe to run again."

    def handle(self, *args: Any, **options: Any) -> None:
        done = 0
        for attachment_id in Attachment.objects.filter(encrypted=False).values_list(
            "pk", flat=True
        ):
            old_keys: list[str] = []
            with transaction.atomic():
                attachment = (
                    Attachment.objects.select_for_update()
                    .filter(pk=attachment_id, encrypted=False)
                    .first()
                )
                if attachment is None:
                    continue
                fields = ["encrypted"]
                for field in ("storage_key", "preview_key"):
                    key = getattr(attachment, field)
                    if not key:
                        continue
                    with storage.open_file(key, encrypted=False) as plain:
                        setattr(attachment, field, storage.save(plain))
                    old_keys.append(key)
                    fields.append(field)
                attachment.encrypted = True
                attachment.save(update_fields=fields)
                # The plain copies go only once the new keys are saved for good.
                transaction.on_commit(partial(_delete_all, tuple(old_keys)))
            done += 1
        self.stdout.write(f"Encrypted {done} files.")
