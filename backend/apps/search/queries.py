"""Searching messages and files the person may read.

Every query starts from readable_channels, the one read rule (AGENTS.md), so a search can't
find anything in a channel or conversation the person can't open.
"""

from dataclasses import dataclass
from datetime import date

from django.db.models import F, FloatField, Func, Model, QuerySet, Value

from apps.chat.access import readable_channels
from apps.chat.models import Message
from apps.chat.serializers import MESSAGE_PREFETCH
from apps.core.search import boolean_query
from apps.files.models import Attachment
from apps.workspaces.models import Member

PAGE_SIZE = 20


@dataclass(frozen=True)
class Filters:
    channel: int | None = None
    author: str | None = None
    after: date | None = None
    before: date | None = None


class Match(Func):
    """MATCH(column) AGAINST (query IN BOOLEAN MODE); the query is a bound parameter."""

    template = "MATCH(%(expressions)s IN BOOLEAN MODE)"
    arg_joiner = ") AGAINST ("
    output_field = FloatField()

    def __init__(self, column: str, words: list[str]) -> None:
        super().__init__(F(column), Value(boolean_query(words)))


def _page[M: Model](
    found: QuerySet[M], filters: Filters, before_id: int | None, author_field: str
) -> tuple[list[M], int | None]:
    """Narrow by the filters, newest first. Returns a page and the id to continue before."""
    if filters.channel is not None:
        found = found.filter(channel_id=filters.channel)
    if filters.author:
        found = found.filter(**{f"{author_field}__username": filters.author})
    if filters.after:
        found = found.filter(created_at__date__gte=filters.after)
    if filters.before:
        found = found.filter(created_at__date__lte=filters.before)
    if before_id is not None:
        found = found.filter(pk__lt=before_id)
    page = list(found.order_by("-pk")[: PAGE_SIZE + 1])
    more = len(page) > PAGE_SIZE
    page = page[:PAGE_SIZE]
    return page, (page[-1].pk if more else None)


def messages(
    member: Member, words: list[str], filters: Filters, before_id: int | None
) -> tuple[list[Message], int | None]:
    found = (
        Message.objects.filter(
            channel__in=readable_channels(member).values("pk"), deleted_at__isnull=True
        )
        .annotate(score=Match("body", words))
        .filter(score__gt=0)
        .select_related("author", "parent")
        .prefetch_related(*MESSAGE_PREFETCH)
    )
    return _page(found, filters, before_id, "author")


def files(
    member: Member, words: list[str], filters: Filters, before_id: int | None
) -> tuple[list[Attachment], int | None]:
    """Only files that were sent: a file not yet sent is its uploader's alone."""
    found = (
        Attachment.objects.for_workspace(member.workspace)
        .filter(
            channel__in=readable_channels(member).values("pk"),
            message__isnull=False,
            message__deleted_at__isnull=True,
        )
        .annotate(score=Match("name", words))
        .filter(score__gt=0)
        .select_related("workspace", "message", "message__parent")
    )
    return _page(found, filters, before_id, "uploader")
