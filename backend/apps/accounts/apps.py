from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self) -> None:
        # Connects the sign-in, sign-out and deactivation receivers.
        from apps.accounts import devices  # noqa: F401
