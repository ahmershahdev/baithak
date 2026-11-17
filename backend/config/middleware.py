from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

# The API only returns JSON, so nothing in a response should ever load, run or be framed.
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class ApiSecurityHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response.headers.setdefault("Content-Security-Policy", API_CSP)
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response
