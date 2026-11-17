import os
from pathlib import Path

import django_stubs_ext
from django.core.exceptions import ImproperlyConfigured

# Lets Django's generic classes (ModelAdmin, QuerySet) take type parameters at runtime.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

_MISSING = object()


def env(name: str, default: str | object = _MISSING) -> str:
    value = os.environ.get(name)
    if value is not None:
        return value
    if isinstance(default, str):
        return default
    raise ImproperlyConfigured(f"Set the {name} environment variable.")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "drf_spectacular",
    "apps.accounts",
    "apps.workspaces",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.ApiSecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("MYSQL_DATABASE", "baithak"),
        "USER": env("MYSQL_USER", "baithak"),
        "PASSWORD": env("MYSQL_PASSWORD"),
        "HOST": env("MYSQL_HOST", "127.0.0.1"),
        "PORT": env("MYSQL_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
        "TEST": {"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_ai_ci"},
    }
}

REDIS_URL = env("REDIS_URL", "redis://127.0.0.1:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://127.0.0.1:6379/1")
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

AUTH_USER_MODEL = "accounts.User"
# Sign-in throttling counts attempts here, so it has to be shared by every process.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("CACHE_URL", "redis://127.0.0.1:6379/2"),
    }
}

FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173")
# One day, for both password reset and email verification links.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Baithak <no-reply@ahmershah.dev>")

# Email goes out through Resend's SMTP relay; the API key is the SMTP password. Without a key
# (local development) mail is printed to the console instead.
EMAIL_HOST = "smtp.resend.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "resend"
EMAIL_HOST_PASSWORD = env("RESEND_API_KEY", "")
EMAIL_TIMEOUT = 10
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_PASSWORD
    else "django.core.mail.backends.console.EmailBackend"
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"auth": "10/minute"},
    # How many proxies sit in front of the app. 0 means the client address is REMOTE_ADDR and a
    # client-sent X-Forwarded-For is ignored, so nobody can dodge the throttle by forging it.
    "NUM_PROXIES": int(env("NUM_PROXIES", "0")),
}

# Five wrong passwords for one email lock sign-in for that email for 15 minutes, from any IP.
SIGNIN_MAX_FAILURES = 5
SIGNIN_LOCKOUT_SECONDS = 15 * 60

# Google reCAPTCHA. Empty keys turn the check off (local development and tests).
RECAPTCHA_V3_SITE_KEY = env("RECAPTCHA_V3_SITE_KEY", "")
RECAPTCHA_V3_SECRET_KEY = env("RECAPTCHA_V3_SECRET_KEY", "")
RECAPTCHA_V2_SITE_KEY = env("RECAPTCHA_V2_SITE_KEY", "")
RECAPTCHA_V2_SECRET_KEY = env("RECAPTCHA_V2_SECRET_KEY", "")
RECAPTCHA_V3_MIN_SCORE = float(env("RECAPTCHA_V3_MIN_SCORE", "0.5"))

SPECTACULAR_SETTINGS = {
    "TITLE": "Baithak API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# Argon2id for every new or changed password. PBKDF2 stays second so older hashes still verify
# and are rehashed with Argon2id at the next sign-in.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
