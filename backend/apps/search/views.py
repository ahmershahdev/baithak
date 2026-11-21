from typing import cast

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.search import terms
from apps.search import queries
from apps.search.serializers import (
    FileHitSerializer,
    FileResultsSerializer,
    MessageHitSerializer,
    MessageResultsSerializer,
    SearchParamsSerializer,
)
from apps.workspaces.access import membership


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


class MessageSearchView(APIView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "search"

    @extend_schema(
        parameters=[SearchParamsSerializer],
        responses={200: MessageResultsSerializer},
        summary="Search messages you can read, newest first",
    )
    def get(self, request: Request, slug: str) -> Response:
        member = membership(cast(User, request.user), slug)
        words, filters, before_id = _params(request)
        if not words:
            return Response({"terms": [], "results": [], "next": None})
        found, more = queries.messages(member, words, filters, before_id)
        return Response(
            {
                "terms": words,
                "results": [MessageHitSerializer(hit).data for hit in found],
                "next": more,
            }
        )


class FileSearchView(APIView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "search"

    @extend_schema(
        parameters=[SearchParamsSerializer],
        responses={200: FileResultsSerializer},
        summary="Search files you can read by name, newest first",
    )
    def get(self, request: Request, slug: str) -> Response:
        member = membership(cast(User, request.user), slug)
        words, filters, before_id = _params(request)
        if not words:
            return Response({"terms": [], "results": [], "next": None})
        found, more = queries.files(member, words, filters, before_id)
        return Response(
            {
                "terms": words,
                "results": [FileHitSerializer(hit).data for hit in found],
                "next": more,
            }
        )
