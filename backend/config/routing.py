from django.urls import path

from apps.chat.consumers import WorkspaceConsumer

websocket_urlpatterns = [
    # django-stubs types path() for views only; Channels routes ASGI apps through it.
    path("ws/workspaces/<slug:slug>/", WorkspaceConsumer.as_asgi()),  # type: ignore[arg-type]
]
