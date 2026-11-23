"""Checks that a file really is what its type says, all the way through, before it is shared.
The upload view only judged the first bytes; a file can start right and still be broken or
built to attack the program that opens it."""

import io
import warnings
import zipfile

from PIL import Image

from apps.core import files as file_rules

# Images that decode to more pixels than this are checked for structure but not decoded
# (decompression bombs); tasks.make_preview gives them no preview either.
MAX_PIXELS = 40_000_000


def _image_problem(data: bytes) -> str | None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                if image.width * image.height <= MAX_PIXELS:
                    image.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return "The image is too large to check."
    except (OSError, ValueError, SyntaxError):
        return "The image is damaged."
    return None


def _zip_problem(data: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = [
                (info.filename, info.file_size, info.compress_size, info.flag_bits)
                for info in archive.infolist()
            ]
    except (zipfile.BadZipFile, OSError, ValueError):
        return "The archive is damaged."
    return file_rules.archive_problem(entries)


def problem(data: bytes, content_type: str) -> str | None:
    """Why a stored file is refused, or None when it checks out."""
    if content_type in file_rules.IMAGE_TYPES:
        return _image_problem(data)
    if content_type == "application/pdf":
        return file_rules.pdf_problem(data)
    if content_type == "application/zip":
        return _zip_problem(data)
    return file_rules.text_problem(data)
