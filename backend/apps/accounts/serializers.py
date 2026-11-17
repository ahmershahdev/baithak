from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User, username_validator


class UserSerializer(serializers.ModelSerializer[User]):
    email_verified = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "username", "display_name", "email_verified")
        read_only_fields = fields


def check_password_rules(password: str, user: User) -> None:
    try:
        validate_password(password, user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({"password": list(error.messages)}) from error


class HandleField(serializers.CharField):
    # Lowercased before the validators run, so "Amna" is checked (and stored) as "amna".
    def to_internal_value(self, data: Any) -> str:
        return super().to_internal_value(data).lower()


class BotCheckFields(serializers.Serializer[None]):
    """Fields every anonymous form sends: reCAPTCHA tokens and the hidden honeypot."""

    captcha = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    captcha_v2 = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    website = serializers.CharField(required=False, allow_blank=True, max_length=200)


class SignUpSerializer(BotCheckFields):
    email = serializers.EmailField(max_length=254)
    # The uniqueness check is done here rather than by a model validator so the email check
    # can be left out on purpose: a taken email must not be revealed.
    username = HandleField(max_length=30, validators=[username_validator])
    display_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This handle is taken.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        candidate = User(
            email=attrs["email"],
            username=attrs["username"],
            display_name=attrs.get("display_name", ""),
        )
        check_password_rules(attrs["password"], candidate)
        return attrs


class SignInSerializer(BotCheckFields):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class EmailSerializer(BotCheckFields):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class UidTokenSerializer(serializers.Serializer[None]):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)


class PasswordResetConfirmSerializer(UidTokenSerializer):
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)


class DetailSerializer(serializers.Serializer[None]):
    detail = serializers.CharField()


class AuthConfigSerializer(serializers.Serializer[None]):
    recaptcha_v3_site_key = serializers.CharField(allow_blank=True)
    recaptcha_v2_site_key = serializers.CharField(allow_blank=True)


class CaptchaErrorSerializer(serializers.Serializer[None]):
    detail = serializers.CharField()
    captcha = serializers.ChoiceField(choices=["v2"], required=False)
