from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from config.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/workspaces/", include("apps.workspaces.urls")),
    path("api/v1/invitations/", include("apps.workspaces.invitation_urls")),
]

if settings.DEBUG:
    urlpatterns.append(path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"))
