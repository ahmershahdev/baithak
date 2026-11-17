import redis
from django.conf import settings
from django.db import connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET


def _database_ok() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return False
    return True


def _redis_ok() -> bool:
    client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
    try:
        return bool(client.ping())
    except redis.RedisError:
        return False
    finally:
        client.close()


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    checks = {"database": _database_ok(), "redis": _redis_ok()}
    healthy = all(checks.values())
    body = {"status": "ok" if healthy else "error"} | {
        name: "ok" if ok else "error" for name, ok in checks.items()
    }
    return JsonResponse(body, status=200 if healthy else 503)
