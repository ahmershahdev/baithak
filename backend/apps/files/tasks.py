import io
import warnings
from datetime import timedelta

from celery import Task, shared_task
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps

from apps.chat import messages
from apps.core import files as file_rules
from apps.files import inspect, scanning, storage
from apps.files.models import Attachment, Scan

PREVIEW_SIDE = 720
MAX_PIXELS = inspect.MAX_PIXELS
# clamd may be restarting or updating its signatures; back off up to ten minutes a try. After
# the last try the file stays pending and rescan_stuck picks it up again.
MAX_TRIES = 12
STUCK_AFTER = timedelta(minutes=5)


def _finish(attachment_id: int, scan: Scan, detail: str = "") -> None:
    with transaction.atomic():
        # Only a pending file moves on, so two scans of one file (a retry and the sweeper)
        # can't both decide.
        attachment = (
            Attachment.objects.select_for_update()
            .select_related("message")
            .filter(pk=attachment_id, scan=Scan.PENDING)
            .first()
        )
        if attachment is None:
            return
        attachment.scan = scan
        attachment.scan_detail = detail[:200]
        attachment.scanned_at = timezone.now()
        attachment.save(update_fields=["scan", "scan_detail", "scanned_at"])
        if scan != Scan.CLEAN:
            key = attachment.storage_key
            transaction.on_commit(lambda: storage.delete(key))
        elif attachment.content_type in file_rules.IMAGE_TYPES:
            transaction.on_commit(lambda: make_preview.delay(attachment_id))
        if attachment.message is not None:
            messages.touch(attachment.message)


@shared_task(bind=True, max_retries=MAX_TRIES)
def scan_file(self: Task[[int], None], attachment_id: int) -> None:
    attachment = Attachment.objects.filter(pk=attachment_id, scan=Scan.PENDING).first()
    if attachment is None:
        return
    data = storage.read_all(attachment.storage_key, encrypted=attachment.encrypted)
    if refused := inspect.problem(data, attachment.content_type):
        _finish(attachment_id, Scan.DAMAGED, refused)
        return
    try:
        verdict = scanning.scan(data)
    except scanning.ScanUnavailable as error:
        countdown = min(600, 15 * 2**self.request.retries)
        raise self.retry(exc=error, countdown=countdown) from error
    if verdict.clean:
        _finish(attachment_id, Scan.CLEAN)
    else:
        _finish(attachment_id, Scan.INFECTED, verdict.detail)


@shared_task
def rescan_stuck() -> None:
    """Queues again any file still pending a while after upload: its scan ran out of tries,
    or the worker running it stopped."""
    cutoff = timezone.now() - STUCK_AFTER
    stuck = Attachment.objects.filter(scan=Scan.PENDING, created_at__lt=cutoff)
    for attachment_id in stuck.values_list("pk", flat=True)[:500]:
        scan_file.delay(attachment_id)


@shared_task
def make_preview(attachment_id: int) -> None:
    """A smaller WebP of an uploaded image, upright and without its metadata."""
    attachment = Attachment.objects.filter(pk=attachment_id).select_related("message").first()
    if attachment is None or attachment.preview_key or attachment.scan != Scan.CLEAN:
        return
    # A preview is stored like its original; plain files from before encryption get none.
    if not attachment.encrypted:
        return
    try:
        with (
            warnings.catch_warnings(),
            storage.open_file(attachment.storage_key, encrypted=attachment.encrypted) as source,
            Image.open(io.BytesIO(source.read())) as image,
        ):
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            if image.width * image.height > MAX_PIXELS:
                return
            upright = ImageOps.exif_transpose(image)
            width, height = upright.size
            upright.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE))
            if upright.mode not in ("RGB", "RGBA"):
                upright = upright.convert("RGBA")
            out = io.BytesIO()
            upright.save(out, "WEBP", quality=80)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError, ValueError):
        # Not an image Pillow can read safely: it stays a plain download.
        return
    attachment.preview_key = storage.save_bytes(out.getvalue())
    attachment.width, attachment.height = width, height
    attachment.save(update_fields=["preview_key", "width", "height"])
    if attachment.message is not None:
        messages.touch(attachment.message)
