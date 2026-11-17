from typing import Any, cast

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import captcha, guards, tasks
from apps.accounts.models import User
from apps.accounts.serializers import (
    AuthConfigSerializer,
    CaptchaErrorSerializer,
    DetailSerializer,
    EmailSerializer,
    PasswordResetConfirmSerializer,
    SignInSerializer,
    SignUpSerializer,
    UidTokenSerializer,
    UserSerializer,
    check_password_rules,
)
from apps.accounts.tokens import email_verification_token, password_reset_token, user_from_uid

CHECK_EMAIL = "If the address can be used, an email is on its way."
BAD_LINK = "This link is not valid or has expired."
WRONG_CREDENTIALS = "The email or password is wrong."
LOCKED = "Too many wrong passwords for this account. Try again in 15 minutes."
CAPTCHA_DOUBT = "Please confirm you are a person."
CAPTCHA_FAILED = "The person check failed. Try it again."


# DRF's SessionAuthentication checks CSRF only for signed-in requests. Sign-in and sign-up are
# anonymous, so without this a hostile page could sign a visitor into the attacker's account.
@method_decorator(csrf_protect, name="dispatch")
class AnonymousAPIView(APIView):
    permission_classes = (AllowAny,)
    throttle_scope = "auth"
    captcha_action = ""

    def captcha_problem(self, request: Request) -> Response | None:
        """A 400 asking for (or rejecting) the person check, or None when it passes."""
        verdict = captcha.verify(request.data, self.captcha_action, request.META.get("REMOTE_ADDR"))
        if verdict == captcha.Verdict.ALLOW:
            return None
        detail = CAPTCHA_DOUBT if verdict == captcha.Verdict.CHALLENGE else CAPTCHA_FAILED
        body: dict[str, str] = {"detail": detail}
        if settings.RECAPTCHA_V2_SECRET_KEY:
            body["captcha"] = "v2"
        return Response(body, status=status.HTTP_400_BAD_REQUEST)


def _send_after_commit(task: Any, user_id: int) -> None:
    transaction.on_commit(lambda: task.delay(user_id))


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses={204: None}, summary="Set the CSRF cookie")
    def get(self, request: Request) -> Response:
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuthConfigView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses={200: AuthConfigSerializer}, summary="Public settings for auth forms")
    def get(self, request: Request) -> Response:
        # Site keys are public by design: Google expects them in the page.
        return Response(
            {
                "recaptcha_v3_site_key": settings.RECAPTCHA_V3_SITE_KEY,
                "recaptcha_v2_site_key": settings.RECAPTCHA_V2_SITE_KEY,
            }
        )


class SignUpView(AnonymousAPIView):
    captcha_action = "signup"

    @extend_schema(
        request=SignUpSerializer,
        responses={202: DetailSerializer, 400: CaptchaErrorSerializer},
        summary="Sign up",
    )
    def post(self, request: Request) -> Response:
        if guards.caught_by_honeypot(request.data):
            return Response({"detail": CHECK_EMAIL}, status=status.HTTP_202_ACCEPTED)
        if problem := self.captcha_problem(request):
            return problem
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            existing = User.objects.filter(email=data["email"]).first()
            if existing is not None:
                _send_after_commit(tasks.send_account_exists_email, existing.pk)
            else:
                user = User.objects.create_user(
                    email=data["email"],
                    username=data["username"],
                    display_name=data.get("display_name", ""),
                    password=data["password"],
                )
                _send_after_commit(tasks.send_verification_email, user.pk)
        return Response({"detail": CHECK_EMAIL}, status=status.HTTP_202_ACCEPTED)


class SignInView(AnonymousAPIView):
    captcha_action = "signin"

    @extend_schema(
        request=SignInSerializer,
        responses={200: UserSerializer, 400: CaptchaErrorSerializer, 429: DetailSerializer},
        summary="Sign in",
    )
    def post(self, request: Request) -> Response:
        if guards.caught_by_honeypot(request.data):
            return Response({"detail": WRONG_CREDENTIALS}, status=status.HTTP_400_BAD_REQUEST)
        if problem := self.captcha_problem(request):
            return problem
        serializer = SignInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        if guards.account_locked(email):
            return Response({"detail": LOCKED}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        user = authenticate(
            request._request, email=email, password=serializer.validated_data["password"]
        )
        if user is None:
            guards.note_failure(email)
            return Response({"detail": WRONG_CREDENTIALS}, status=status.HTTP_400_BAD_REQUEST)
        guards.clear_failures(email)
        login(request._request, user)
        return Response(UserSerializer(user).data)


class SignOutView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(request=None, responses={204: None}, summary="Sign out")
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: UserSerializer}, summary="The signed-in person")
    def get(self, request: Request) -> Response:
        return Response(UserSerializer(cast(User, request.user)).data)


class VerifyEmailView(AnonymousAPIView):
    @extend_schema(
        request=UidTokenSerializer,
        responses={200: UserSerializer, 400: DetailSerializer},
        summary="Confirm an email address and sign in",
    )
    def post(self, request: Request) -> Response:
        serializer = UidTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = user_from_uid(serializer.validated_data["uid"])
        if user is None or not email_verification_token.check_token(
            user, serializer.validated_data["token"]
        ):
            return Response({"detail": BAD_LINK}, status=status.HTTP_400_BAD_REQUEST)
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(UserSerializer(user).data)


class ResendVerificationView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_scope = "auth"

    @extend_schema(request=None, responses={202: DetailSerializer}, summary="Resend the email")
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        if not user.email_verified:
            tasks.send_verification_email.delay(user.pk)
        return Response({"detail": CHECK_EMAIL}, status=status.HTTP_202_ACCEPTED)


class PasswordResetView(AnonymousAPIView):
    captcha_action = "password_reset"

    @extend_schema(
        request=EmailSerializer,
        responses={202: DetailSerializer, 400: CaptchaErrorSerializer},
        summary="Ask for a reset link",
    )
    def post(self, request: Request) -> Response:
        if guards.caught_by_honeypot(request.data):
            return Response({"detail": CHECK_EMAIL}, status=status.HTTP_202_ACCEPTED)
        if problem := self.captcha_problem(request):
            return problem
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email=serializer.validated_data["email"], is_active=True).first()
        if user is not None:
            tasks.send_password_reset_email.delay(user.pk)
        return Response({"detail": CHECK_EMAIL}, status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(AnonymousAPIView):
    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={204: None, 400: DetailSerializer},
        summary="Choose a new password",
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = user_from_uid(serializer.validated_data["uid"])
        if user is None or not password_reset_token.check_token(
            user, serializer.validated_data["token"]
        ):
            return Response({"detail": BAD_LINK}, status=status.HTTP_400_BAD_REQUEST)
        check_password_rules(serializer.validated_data["password"], user)
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)
