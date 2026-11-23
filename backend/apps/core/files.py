"""What may be uploaded, judged from the file's own bytes, never from its name or the type the
browser claims.

SVG and HTML are not served as such: SVG is not accepted, and HTML is plain text, so nothing
uploaded can run script on this origin.
"""

import re
import unicodedata

MAX_SIZE = 25 * 1024 * 1024
# Bytes read to judge a file.
HEAD = 4096

IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
ALLOWED_TYPES = IMAGE_TYPES | {"application/pdf", "application/zip", "text/plain"}

_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"%PDF-", "application/pdf"),
    # Office documents (docx, xlsx, pptx) are zip files too.
    (b"PK\x03\x04", "application/zip"),
    (b"PK\x05\x06", "application/zip"),
)

MAX_NAME = 200


def sniff(head: bytes) -> str | None:
    """The type of a file from its first bytes, or None when it isn't one we take."""
    for signature, content_type in _SIGNATURES:
        if head.startswith(signature):
            return content_type
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return "text/plain" if _is_text(head) else None


def _is_text(head: bytes) -> bool:
    if not head or b"\x00" in head:
        return False
    # The head may end inside a multi-byte character; up to three bytes can be cut.
    for cut in range(4):
        try:
            text = head[: len(head) - cut].decode("utf-8")
        except UnicodeDecodeError:
            continue
        return all(char in "\t\n\r\f" or unicodedata.category(char) != "Cc" for char in text)
    return False


def problem(size: int, content_type: str | None) -> str | None:
    """Why a file is refused, or None when it is fine."""
    if size == 0:
        return "The file is empty."
    if size > MAX_SIZE:
        return f"Files can be up to {MAX_SIZE // (1024 * 1024)} MB."
    if content_type not in ALLOWED_TYPES:
        return "Upload images (PNG, JPEG, GIF, WebP), PDFs, zip or Office files, or plain text."
    return None


def safe_name(name: str) -> str:
    """The name to show and download as: no folders, no control characters, not too long."""
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    clean = "".join(c for c in base if unicodedata.category(c)[0] != "C").strip().strip(".")
    if not clean:
        return "file"
    if len(clean) <= MAX_NAME:
        return clean
    stem, dot, extension = clean.rpartition(".")
    if dot and 0 < len(extension) <= 10:
        return stem[: MAX_NAME - len(extension) - 1] + "." + extension
    return clean[:MAX_NAME]


def shown_inline(content_type: str) -> bool:
    """Only images open in the browser; everything else downloads."""
    return content_type in IMAGE_TYPES


def clamd_verdict(reply: bytes) -> tuple[str, str]:
    """("clean", ""), ("found", signature) or ("error", reason) from a clamd INSTREAM reply,
    which reads "stream: OK", "stream: <signature> FOUND" or "<reason> ERROR"."""
    text = reply.rstrip(b"\0\r\n").decode("utf-8", "replace").strip()
    result = text.split(": ", 1)[-1]
    if result == "OK":
        return "clean", ""
    if result.endswith(" FOUND"):
        return "found", result.removesuffix(" FOUND")
    return "error", result.removesuffix(" ERROR") or "No answer"


# Archives are opened by the scanner; these limits refuse ones built to exhaust it first.
MAX_ENTRIES = 10_000
MAX_UNPACKED = 250 * 1024 * 1024
MAX_RATIO = 100
ENCRYPTED_FLAG = 0x1
MACRO_PART = "vbaproject.bin"


def archive_problem(entries: list[tuple[str, int, int, int]]) -> str | None:
    """Why a zip is refused, from its entries as (name, unpacked size, packed size, flags)."""
    if len(entries) > MAX_ENTRIES:
        return "The archive holds too many files to check."
    if sum(size for _, size, _, _ in entries) > MAX_UNPACKED:
        return "The archive unpacks to more than we can check."
    for name, size, packed, flags in entries:
        if flags & ENCRYPTED_FLAG:
            return "Password-protected archives can't be checked."
        if size > MAX_RATIO * max(packed, 1):
            return "The archive is packed too tightly to check safely."
        if name.replace("\\", "/").rsplit("/", 1)[-1].lower() == MACRO_PART:
            return "Office files with macros are not accepted."
    return None


_PDF_NAME = re.compile(rb"/((?:[A-Za-z0-9]|#[0-9A-Fa-f]{2})+)")
# Actions that run code or open other programs when the PDF is opened.
RISKY_PDF_NAMES = frozenset({"JavaScript", "JS", "Launch"})


def pdf_problem(data: bytes) -> str | None:
    """Why a PDF is refused. Names may hide behind #xx escapes (/J#61vaScript), so they are
    decoded before comparing."""
    if b"%%EOF" not in data[-2048:]:
        return "The PDF is incomplete or damaged."
    for match in _PDF_NAME.finditer(data):
        name = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), match.group(1))
        if name.decode("latin-1") in RISKY_PDF_NAMES:
            return "PDFs that run scripts or open programs are not accepted."
    return None


def text_problem(data: bytes) -> str | None:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return "The text file isn't valid UTF-8."
    return None
