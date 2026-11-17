from rest_framework.request import Request
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView


class SendThrottle(ScopedRateThrottle):
    """The "post" scope, counted for POST only: reading history is never limited."""

    def allow_request(self, request: Request, view: APIView) -> bool:
        if request.method != "POST":
            return True
        return super().allow_request(request, view)
