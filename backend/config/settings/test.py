import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-secret")
os.environ.setdefault("MYSQL_PASSWORD", "baithak")

from config.settings.base import *  # noqa: F403

ALLOWED_HOSTS = ["testserver", "localhost"]
# Fast hashing keeps the suite quick; tests/accounts/test_hashing.py checks the real list.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
FRONTEND_URL = "http://web.test"
RECAPTCHA_V3_SECRET_KEY = ""
RECAPTCHA_V2_SECRET_KEY = ""
