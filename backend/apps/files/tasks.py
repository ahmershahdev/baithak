import io
import warnings

from celery import shared_task
from PIL import Image, ImageOps

from apps.chat import messages
from apps.files import storage
from apps.files.models import Attachment

PREVIEW_SIDE = 720
# Images that decode to more pixels than this get no preview (decompression bombs). Pillow
# only warns between its limit and twice it, so the size is checked here before decoding.
MAX_PIXELS = 40_000_000


@shared_task
def make_preview(attachment_id: int) -> None:
    """A smaller WebP of an uploaded image, upright and without its metadata."""
    attachment = Attachment.objects.filter(pk=attachment_id).select_related("message").first()
    if attachment is None or attachment.preview_key:
        return
    try:
        with (
            warnings.catch_warnings(),
            storage.open_file(attachment.storage_key) as source,
            Image.open(source) as image,
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
