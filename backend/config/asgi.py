import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

# The app registry has to be loaded before anything that imports models, so the Channels
# routing (and through it every consumer) is imported only after get_asgi_application().
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from config.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            # types-channels types routes as a private URLPattern subclass that path() never
            # returns, so a plain list of path() results does not type-check.
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))  # type: ignore[arg-type]
        ),
    }
)
