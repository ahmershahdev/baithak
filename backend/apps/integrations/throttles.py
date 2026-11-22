from typing import Any

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle

from apps.core.webhooks import digest


class PerWebhookThrottle(SimpleRateThrottle):
    """Counts calls per incoming webhook, not per address: a leaked URL called from many
    addresses still floods its channel at no more than the `incoming` rate."""

    scope = "incoming"

    def get_cache_key(self, request: Request, view: Any) -> str:
        return self.cache_format % {"scope": self.scope, "ident": digest(view.kwargs["token"])}
