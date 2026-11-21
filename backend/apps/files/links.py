"""Signed, expiring download links. The signature names the file and which version of it;
the download view also checks that the person can still read its channel."""

from django.conf import settings
from django.core import signing
from django.urls import reverse

_SALT = "baithak.files.link"
ORIGINAL, PREVIEW = "original", "preview"


def url(slug: str, attachment_id: int, variant: str) -> str:
    token = signing.dumps([attachment_id, variant], salt=_SALT, compress=False)
    return reverse("files:download", kwargs={"slug": slug, "token": token})


def read(token: str) -> tuple[int, str] | None:
    try:
        value = signing.loads(token, salt=_SALT, max_age=settings.FILE_LINK_MAX_AGE)
    except signing.BadSignature:
        return None
    match value:
        case [int(attachment_id), str(variant)] if variant in (ORIGINAL, PREVIEW):
            return attachment_id, variant
    return None
