from channels.routing import ProtocolTypeRouter

from config.asgi import application
from config.celery import app as celery_app


def test_asgi_routes_http_and_websocket() -> None:
    assert isinstance(application, ProtocolTypeRouter)
    assert set(application.application_mapping) == {"http", "websocket"}


def test_celery_reads_django_settings() -> None:
    assert celery_app.conf.task_always_eager is True
