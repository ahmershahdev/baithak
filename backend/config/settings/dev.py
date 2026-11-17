import os

os.environ.setdefault("DJANGO_SECRET_KEY", "dev-only-not-a-secret")
os.environ.setdefault("MYSQL_PASSWORD", "baithak")

from config.settings.base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
# The Vite dev server proxies to the backend under the backend's own host, so the browser's
# Origin (the Vite port) has to be trusted explicitly for Django's CSRF origin check.
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
