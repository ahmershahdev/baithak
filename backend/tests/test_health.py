import pytest
import redis
from django.db.utils import OperationalError
from django.test import Client


@pytest.mark.django_db
def test_health_reports_ok_when_database_and_redis_answer(client: Client) -> None:
    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "redis": "ok"}


@pytest.mark.django_db
def test_health_is_503_when_database_fails(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_cursor(*args: object, **kwargs: object) -> None:
        raise OperationalError("database down")

    monkeypatch.setattr("config.health.connection.cursor", broken_cursor)

    response = client.get("/health/")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "error", "redis": "ok"}


@pytest.mark.django_db
def test_health_is_503_when_redis_fails(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_ping(self: redis.Redis) -> bool:
        raise redis.ConnectionError("redis down")

    monkeypatch.setattr(redis.Redis, "ping", broken_ping)

    response = client.get("/health/")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "ok", "redis": "error"}


def test_health_rejects_post(client: Client) -> None:
    assert client.post("/health/").status_code == 405
