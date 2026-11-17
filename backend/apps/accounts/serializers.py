from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.models import User, username_validator
from apps.core import handles
from apps.core.passwords import MAX_LENGTH


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
    captcha = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    captcha_v2 = serializers.CharField(required=False, allow_blank=True, max_length=4000)
    website = serializers.CharField(required=False, allow_blank=True, max_length=200)


def check_handle(value: str) -> str | None:
    """Why this handle can't be taken, or None. Shared by sign-up and the live check."""
    problem = handles.problem(value)
    if problem:
        return problem
    if User.objects.filter(username=value).exists():
        return "This handle is taken."
    return None


class SignUpSerializer(BotCheckFields):
    email = serializers.EmailField(max_length=254)
    username = HandleField(max_length=30, validators=[username_validator])
    display_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, max_length=MAX_LENGTH, trim_whitespace=False)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_username(self, value: str) -> str:
        problem = check_handle(value)
        if problem:
            raise serializers.ValidationError(problem)
        return value

    def validate_display_name(self, value: str) -> str:
        if handles.is_offensive(value):
            raise serializers.ValidationError("This name is not allowed.")
        return value.strip()

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
    password = serializers.CharField(write_only=True, max_length=MAX_LENGTH, trim_whitespace=False)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class EmailSerializer(BotCheckFields):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class UidTokenSerializer(serializers.Serializer[None]):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)


class PasswordResetConfirmSerializer(serializers.Serializer[None]):
    """The code from the email, and who it is for: `uid` from the emailed link, or `email`."""

    uid = serializers.CharField(max_length=64, required=False)
    email = serializers.EmailField(max_length=254, required=False)
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Enter the 6 digits."})
    password = serializers.CharField(write_only=True, max_length=MAX_LENGTH, trim_whitespace=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("uid") and not attrs.get("email"):
            raise serializers.ValidationError({"email": ["Enter your email."]})
        if attrs.get("email"):
            attrs["email"] = attrs["email"].strip().lower()
        return attrs


class AvailabilityRequestSerializer(serializers.Serializer[None]):
    email = serializers.CharField(max_length=254, required=False, allow_blank=True)
    username = serializers.CharField(max_length=60, required=False, allow_blank=True)


class AvailabilitySerializer(serializers.Serializer[None]):
    available = serializers.BooleanField()
    message = serializers.CharField(allow_blank=True)


class AvailabilityResultSerializer(serializers.Serializer[None]):
    email = AvailabilitySerializer(required=False)
    username = AvailabilitySerializer(required=False)


class ContactSerializer(BotCheckFields):
    name = serializers.CharField(max_length=80)
    email = serializers.EmailField(max_length=254)
    message = serializers.CharField(max_length=5000, min_length=10)


class DetailSerializer(serializers.Serializer[None]):
    detail = serializers.CharField()


class AuthConfigSerializer(serializers.Serializer[None]):
    recaptcha_v3_site_key = serializers.CharField(allow_blank=True)
    recaptcha_v2_site_key = serializers.CharField(allow_blank=True)


class CaptchaErrorSerializer(serializers.Serializer[None]):
    detail = serializers.CharField()
    captcha = serializers.ChoiceField(choices=["v2"], required=False)
