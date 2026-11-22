from typing import Any, cast

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.search import terms
from apps.issues.access import projects_member
from apps.search import queries
from apps.search.serializers import (
    FileHitSerializer,
    FileResultsSerializer,
    IssueHitSerializer,
    IssueResultsSerializer,
    MessageHitSerializer,
    MessageResultsSerializer,
    SearchParamsSerializer,
)
from apps.workspaces.access import membership
from apps.workspaces.models import Member


def _params(request: Request) -> tuple[list[str], queries.Filters, int | None]:
    params = SearchParamsSerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    data = params.validated_data
    filters = queries.Filters(
        channel=data.get("channel"),
        author=data.get("author") or None,
        after=data.get("after"),
        before=data.get("before"),
    )
    return terms(data["q"]), filters, data.get("before_id")


class _SearchView(APIView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "search"

    def _search(
        self, member: Member, words: list[str], filters: queries.Filters, before_id: int | None
    ) -> tuple[list[dict[str, Any]], int | None]:
        raise NotImplementedError

    def _member(self, user: User, slug: str) -> Member:
        return membership(user, slug)

    def _respond(self, request: Request, slug: str) -> Response:
        member = self._member(cast(User, request.user), slug)
        words, filters, before_id = _params(request)
        if not words:
            return Response({"terms": [], "results": [], "next": None})
        results, more = self._search(member, words, filters, before_id)
        return Response({"terms": words, "results": results, "next": more})


class MessageSearchView(_SearchView):
    def _search(
        self, member: Member, words: list[str], filters: queries.Filters, before_id: int | None
    ) -> tuple[list[dict[str, Any]], int | None]:
        found, more = queries.messages(member, words, filters, before_id)
        return [dict(MessageHitSerializer(hit).data) for hit in found], more

    @extend_schema(
        parameters=[SearchParamsSerializer],
        responses={200: MessageResultsSerializer},
        summary="Search messages you can read, newest first",
    )
    def get(self, request: Request, slug: str) -> Response:
        return self._respond(request, slug)


class FileSearchView(_SearchView):
    def _search(
        self, member: Member, words: list[str], filters: queries.Filters, before_id: int | None
    ) -> tuple[list[dict[str, Any]], int | None]:
        found, more = queries.files(member, words, filters, before_id)
        return [dict(FileHitSerializer(hit).data) for hit in found], more

    @extend_schema(
        parameters=[SearchParamsSerializer],
        responses={200: FileResultsSerializer},
        summary="Search files you can read by name, newest first",
    )
    def get(self, request: Request, slug: str) -> Response:
        return self._respond(request, slug)


class IssueSearchView(_SearchView):
    def _member(self, user: User, slug: str) -> Member:
        return projects_member(user, slug)

    def _search(
        self, member: Member, words: list[str], filters: queries.Filters, before_id: int | None
    ) -> tuple[list[dict[str, Any]], int | None]:
        found, more = queries.issues(member, words, filters, before_id)
        return [dict(IssueHitSerializer(hit).data) for hit in found], more

    @extend_schema(
        parameters=[SearchParamsSerializer],
        responses={200: IssueResultsSerializer},
        summary="Search issues by title and description, newest first; 404 for guests",
    )
    def get(self, request: Request, slug: str) -> Response:
        return self._respond(request, slug)
