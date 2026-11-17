import os

os.environ.setdefault("DJANGO_SECRET_KEY", "dev-only-not-a-secret")
os.environ.setdefault("MYSQL_PASSWORD", "baithak")

from config.settings.base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
