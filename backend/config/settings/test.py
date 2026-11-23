import os
import tempfile
from pathlib import Path

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-secret")
os.environ.setdefault("MYSQL_PASSWORD", "baithak")
# A fixed key for tests only; real keys come from the environment.
os.environ.setdefault("FILES_ENCRYPTION_KEYS", "dGVzdC1vbmx5LWtleS1ub3QtYS1zZWNyZXQtMzJieXQ=")

from config.settings.base import *  # noqa: F403

ALLOWED_HOSTS = ["testserver", "localhost"]
# Fast hashing keeps the suite quick; tests/accounts/test_hardening.py checks the real list.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
FRONTEND_URL = "http://web.test"
RECAPTCHA_V3_SECRET_KEY = ""
RECAPTCHA_V2_SECRET_KEY = ""
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
# Real Redis, kept apart from development's keys; tests/chat/test_websockets.py clears it.
PRESENCE_KEY_PREFIX = "test-presence"
FILES_ROOT = Path(tempfile.gettempdir()) / "baithak-test-files"
# Clean unless the file holds the EICAR test string (apps/files/scanning.py).
FILE_SCANNER = "fake"
