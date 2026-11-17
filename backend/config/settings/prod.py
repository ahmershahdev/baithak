from config.settings.base import *  # noqa: F403
from config.settings.base import env, env_list

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "baithak.ahmershah.dev")
CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]

# TLS ends at the reverse proxy, which sets X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# Container health checks call the app directly over plain HTTP.
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Baithak <no-reply@ahmershah.dev>")

# baithak is one subdomain of ahmershah.dev; it can't promise HTTPS for its sibling subdomains,
# so HSTS stays on this host only and the domain is not submitted for preload.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
