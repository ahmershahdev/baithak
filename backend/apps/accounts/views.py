from typing import Any, cast

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import captcha, guards, lockout, reset_codes, tasks
from apps.accounts.models import ContactMessage, User, username_validator
from apps.accounts.serializers import (
    AuthConfigSerializer,
    AvailabilityRequestSerializer,
    AvailabilityResultSerializer,
    CaptchaErrorSerializer,
    ContactSerializer,
    DetailSerializer,
    EmailSerializer,
    PasswordResetConfirmSerializer,
    SignInSerializer,
    SignUpSerializer,
    UidTokenSerializer,
    UserSerializer,
    check_handle,
    check_password_rules,
)
from apps.accounts.tokens import email_verification_token, user_from_uid

CHECK_EMAIL = "If the address can be used, an email is on its way."
BAD_LINK = "This link is not valid or has expired."
WRONG_CREDENTIALS = "The email or password is wrong."
LOCKED = (
    "This account is locked after too many wrong attempts. Try again later, or write to "
    f"{settings.SUPPORT_EMAIL} if you need help."
)
BAD_CODE = "The code is wrong or has expired. Ask for a new one if you need to."
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
        try:
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
        except IntegrityError:
            # The unique indexes are the lock: two sign-ups racing for one handle or email
            # can't both win. The email case answers like any taken email.
            if User.objects.filter(username=data["username"]).exists():
                return Response(
                    {"username": ["This handle is taken."]}, status=status.HTTP_400_BAD_REQUEST
                )
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
        account = User.objects.filter(email=email).first()
        if (account and lockout.blocked(account)) or (not account and guards.account_locked(email)):
            return Response({"detail": LOCKED}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        user = authenticate(
            request._request, email=email, password=serializer.validated_data["password"]
        )
        if user is None:
            if account:
                lockout.record_failure(account)
            else:
                guards.note_failure(email)
            return Response({"detail": WRONG_CREDENTIALS}, status=status.HTTP_400_BAD_REQUEST)
        lockout.record_success(user)
        login(request._request, user)
        return Response(UserSerializer(user).data)


class SignOutView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(request=None, responses={204: None}, summary="Sign out")
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        responses={200: UserSerializer, 204: None},
        summary="The signed-in person; 204 when nobody is signed in",
    )
    def get(self, request: Request) -> Response:
        if not request.user.is_authenticated:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(UserSerializer(request.user).data)


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
        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email, is_active=True).first()
        # The answer never changes, so a flood of requests can't tell whether mail went out.
        if user is not None and not lockout.blocked(user) and guards.allow_reset_request(email):
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
        data = serializer.validated_data
        user = (
            user_from_uid(data["uid"])
            if data.get("uid")
            else User.objects.filter(email=data["email"], is_active=True).first()
        )
        key = data.get("email") or data.get("uid", "")
        if (user and lockout.blocked(user)) or (not user and guards.account_locked(key)):
            return Response({"detail": LOCKED}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        if user is None:
            guards.note_failure(key)
            return Response({"detail": BAD_CODE}, status=status.HTTP_400_BAD_REQUEST)
        check_password_rules(data["password"], user)
        if not reset_codes.redeem(user, data["code"]):
            lockout.record_failure(user)
            return Response({"detail": BAD_CODE}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(data["password"])
        user.save(update_fields=["password"])
        lockout.record_success(user)
        tasks.send_password_changed_email.delay(user.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AvailabilityView(APIView):
    """Live checks for the sign-up form.

    This tells anyone whether an email has an account, which sign-up itself never does; the
    tight throttle is what keeps it from being a list of members.
    """

    permission_classes = (AllowAny,)
    throttle_scope = "availability"

    @extend_schema(
        request=AvailabilityRequestSerializer,
        responses={200: AvailabilityResultSerializer},
        summary="Is this email or handle free?",
    )
    def post(self, request: Request) -> Response:
        serializer = AvailabilityRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result: dict[str, dict[str, object]] = {}
        email = serializer.validated_data.get("email", "").strip().lower()
        if email:
            taken = User.objects.filter(email=email).exists()
            result["email"] = {
                "available": not taken,
                "message": "This email already has an account. Sign in instead?" if taken else "",
            }
        handle = serializer.validated_data.get("username", "").strip().lower()
        if handle:
            problem = None
            try:
                username_validator(handle)
            except DjangoValidationError as error:
                problem = error.messages[0]
            problem = problem or check_handle(handle)
            result["username"] = {"available": problem is None, "message": problem or ""}
        return Response(result)


class ContactView(AnonymousAPIView):
    captcha_action = "contact"
    throttle_scope = "contact"

    @extend_schema(
        request=ContactSerializer,
        responses={202: DetailSerializer, 400: CaptchaErrorSerializer},
        summary="Write to the Baithak team",
    )
    def post(self, request: Request) -> Response:
        thanks = {"detail": "Thank you. We will reply by email."}
        if guards.caught_by_honeypot(request.data):
            return Response(thanks, status=status.HTTP_202_ACCEPTED)
        if problem := self.captcha_problem(request):
            return problem
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            message = ContactMessage.objects.create(
                name=data["name"], email=data["email"].lower(), message=data["message"]
            )
            _send_after_commit(tasks.send_contact_message, message.pk)
        return Response(thanks, status=status.HTTP_202_ACCEPTED)
