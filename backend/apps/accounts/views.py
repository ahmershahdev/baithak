from typing import Any, cast

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import (
    captcha,
    deletion,
    devices,
    external,
    guards,
    lockout,
    oidc,
    reset_codes,
    tasks,
    two_step,
)
from apps.accounts.models import ContactMessage, Device, User, username_validator
from apps.accounts.serializers import (
    AuthConfigSerializer,
    AvailabilityRequestSerializer,
    AvailabilityResultSerializer,
    CaptchaErrorSerializer,
    CodeSerializer,
    ContactSerializer,
    DeleteAccountSerializer,
    DetailSerializer,
    DeviceSerializer,
    EmailSerializer,
    NotificationSettingsSerializer,
    OwnsWorkspacesSerializer,
    PasswordAndCodeSerializer,
    PasswordResetConfirmSerializer,
    RecoveryCodesSerializer,
    SignedOutSerializer,
    SignInSerializer,
    SignUpSerializer,
    TwoStepNeededSerializer,
    TwoStepSetupSerializer,
    TwoStepStatusSerializer,
    UidTokenSerializer,
    UserSerializer,
    check_handle,
    check_password_rules,
)
from apps.accounts.tokens import email_verification_token, user_from_uid
from apps.core import devices as device_rules

CHECK_EMAIL = "If the address can be used, an email is on its way."
BAD_LINK = "This link is not valid or has expired."
WRONG_CREDENTIALS = "The email or password is wrong."
LOCKED = (
    "This account is locked after too many wrong attempts. Try again later, or write to "
    f"{settings.SUPPORT_EMAIL} if you need help."
)
CONFIRM_FAILED = "The password is wrong."
EMAIL_MISMATCH = "That is not the email address of this account."
HAND_OVER = "Make someone else an owner of these workspaces first, or remove everyone else."
BAD_CODE = "The code is wrong or has expired. Ask for a new one if you need to."
CAPTCHA_DOUBT = "Please confirm you are a person."
CAPTCHA_FAILED = "The person check failed. Try it again."
TWO_STEP_NEEDED = "Enter the code from your authenticator app."
WRONG_TWO_STEP_CODE = "That code is wrong or was already used."
SIGN_IN_AGAIN = "Sign in again: the code step timed out."
CONFIRM_EMAIL_FIRST = "Confirm your email before turning on two-step sign-in."
PROVIDER_ONLY = (
    "Two-step sign-in protects password sign-in. Set a password first, with Forgot your "
    "password on the sign-in page."
)
# A password that passed waits this long for its second step.
TWO_STEP_SECONDS = 5 * 60
PENDING_USER, PENDING_UNTIL = "two_step_user", "two_step_until"


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
                "providers": ["google"] if oidc.google() else [],
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
        responses={
            200: UserSerializer,
            202: TwoStepNeededSerializer,
            400: CaptchaErrorSerializer,
            429: DetailSerializer,
        },
        summary="Sign in; 202 when a two-step code is needed next",
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
        if two_step.is_on(user):
            # Not signed in yet: the session only remembers who passed the password, briefly.
            request.session[PENDING_USER] = user.pk
            request.session[PENDING_UNTIL] = timezone.now().timestamp() + TWO_STEP_SECONDS
            return Response(
                {"detail": TWO_STEP_NEEDED, "two_step": True}, status=status.HTTP_202_ACCEPTED
            )
        lockout.record_success(user)
        login(request._request, user)
        return Response(UserSerializer(user).data)


class SignInTwoStepView(AnonymousAPIView):
    @extend_schema(
        request=CodeSerializer,
        responses={200: UserSerializer, 400: DetailSerializer, 429: DetailSerializer},
        summary="Finish signing in with a code from the authenticator app or a recovery code",
    )
    def post(self, request: Request) -> Response:
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = request.session.get(PENDING_USER)
        until = request.session.get(PENDING_UNTIL, 0)
        user = User.objects.filter(pk=user_id, is_active=True).first() if user_id else None
        if user is None or until < timezone.now().timestamp():
            return Response({"detail": SIGN_IN_AGAIN}, status=status.HTTP_400_BAD_REQUEST)
        if lockout.blocked(user):
            request.session.pop(PENDING_USER, None)
            return Response({"detail": LOCKED}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        used = two_step.check(user, serializer.validated_data["code"])
        if used is None:
            # Wrong codes climb the same lockout ladder as wrong passwords.
            lockout.record_failure(user)
            return Response({"detail": WRONG_TWO_STEP_CODE}, status=status.HTTP_400_BAD_REQUEST)
        request.session.pop(PENDING_USER, None)
        request.session.pop(PENDING_UNTIL, None)
        lockout.record_success(user)
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        if used == two_step.Used.RECOVERY:
            tasks.send_two_step_email.delay(user.pk, "recovery")
        return Response(UserSerializer(user).data)


def _wrong_password_or_code(user: User, data: dict[str, str]) -> Response | None:
    if not user.check_password(data["password"]):
        return Response({"detail": CONFIRM_FAILED}, status=status.HTTP_400_BAD_REQUEST)
    if two_step.check(user, data["code"]) is None:
        return Response({"detail": WRONG_TWO_STEP_CODE}, status=status.HTTP_400_BAD_REQUEST)
    return None


class TwoStepView(APIView):
    throttle_scope = "auth"

    @extend_schema(responses={200: TwoStepStatusSerializer}, summary="My two-step sign-in")
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        return Response(
            {"enabled": two_step.is_on(user), "recovery_codes_left": two_step.codes_left(user)}
        )


class TwoStepSetupView(APIView):
    throttle_scope = "auth"

    @extend_schema(
        request=None,
        responses={200: TwoStepSetupSerializer, 400: DetailSerializer, 403: DetailSerializer},
        summary="Start setting up two-step sign-in: a new key for the authenticator app",
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        # An email link signs an unverified person in, so two-step must wait for a verified
        # address; otherwise the link would be a way around it.
        if not user.email_verified:
            return Response({"detail": CONFIRM_EMAIL_FIRST}, status=status.HTTP_403_FORBIDDEN)
        # Two-step guards password sign-in only (a provider sign-in skips it), and turning it
        # off needs the password.
        if not user.has_usable_password():
            return Response({"detail": PROVIDER_ONLY}, status=status.HTTP_403_FORBIDDEN)
        if two_step.is_on(user):
            return Response(
                {"detail": "Two-step sign-in is already on."}, status=status.HTTP_400_BAD_REQUEST
            )
        secret, uri = two_step.start(user)
        return Response({"secret": secret, "uri": uri})


class TwoStepEnableView(APIView):
    throttle_scope = "auth"

    @extend_schema(
        request=CodeSerializer,
        responses={200: RecoveryCodesSerializer, 400: DetailSerializer},
        summary="Turn two-step sign-in on with a first code from the app",
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        serializer = CodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        codes = two_step.confirm(user, serializer.validated_data["code"])
        if codes is None:
            return Response({"detail": WRONG_TWO_STEP_CODE}, status=status.HTTP_400_BAD_REQUEST)
        tasks.send_two_step_email.delay(user.pk, "on")
        return Response({"recovery_codes": codes})


class TwoStepDisableView(APIView):
    throttle_scope = "auth"

    @extend_schema(
        request=PasswordAndCodeSerializer,
        responses={204: None, 400: DetailSerializer},
        summary="Turn two-step sign-in off",
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        serializer = PasswordAndCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if refused := _wrong_password_or_code(user, serializer.validated_data):
            return refused
        two_step.turn_off(user)
        tasks.send_two_step_email.delay(user.pk, "off")
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecoveryCodesView(APIView):
    throttle_scope = "auth"

    @extend_schema(
        request=PasswordAndCodeSerializer,
        responses={200: RecoveryCodesSerializer, 400: DetailSerializer},
        summary="Replace my recovery codes; the old ones stop working",
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        serializer = PasswordAndCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not two_step.is_on(user):
            return Response(
                {"detail": "Turn on two-step sign-in first."}, status=status.HTTP_400_BAD_REQUEST
            )
        if refused := _wrong_password_or_code(user, serializer.validated_data):
            return refused
        codes = two_step.new_codes(user)
        tasks.send_two_step_email.delay(user.pk, "codes")
        return Response({"recovery_codes": codes})


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


class DeleteAccountView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_scope = "auth"

    @extend_schema(
        request=DeleteAccountSerializer,
        responses={204: None, 400: DetailSerializer, 409: OwnsWorkspacesSerializer},
        summary="Delete my account; my posts stay in shared workspaces with no author",
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        serializer = DeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        confirmed = (
            user.check_password(data.get("password", ""))
            if user.has_usable_password()
            else data.get("email", "").strip().lower() == user.email
        )
        if not confirmed:
            problem = CONFIRM_FAILED if user.has_usable_password() else EMAIL_MISMATCH
            return Response({"detail": problem}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                devices.end_all(user)
                deletion.delete_account(user)
        except deletion.OwnsWorkspaces as blocked:
            body = {
                "detail": HAND_OVER,
                "workspaces": [{"slug": w.slug, "name": w.name} for w in blocked.workspaces],
            }
            return Response(body, status=status.HTTP_409_CONFLICT)
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        devices.end_all(user)
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


class NotificationSettingsView(APIView):
    @extend_schema(responses={200: NotificationSettingsSerializer}, summary="My email settings")
    def get(self, request: Request) -> Response:
        return Response(NotificationSettingsSerializer(cast(User, request.user)).data)

    @extend_schema(
        request=NotificationSettingsSerializer,
        responses={200: NotificationSettingsSerializer},
        summary="Change my email settings and quiet hours",
    )
    def patch(self, request: Request) -> Response:
        serializer = NotificationSettingsSerializer(
            cast(User, request.user), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DevicesView(APIView):
    @extend_schema(
        responses={200: DeviceSerializer(many=True)},
        summary="Where I am signed in, most recently used first",
    )
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        current = request.session.get(devices.SESSION_KEY)
        rows = Device.objects.filter(user=user).order_by("-last_seen_at", "-pk")
        return Response(
            [
                {
                    "id": row.pk,
                    "name": device_rules.label(row.user_agent),
                    "created_at": row.created_at,
                    "last_seen_at": row.last_seen_at,
                    "current": row.pk == current,
                }
                for row in rows
            ]
        )


class DeviceView(APIView):
    throttle_scope = "auth"

    @extend_schema(
        request=None,
        responses={204: None, 404: DetailSerializer},
        summary="Sign one of my devices out; its open tabs close their live connection",
    )
    def delete(self, request: Request, device_id: int) -> Response:
        if not devices.end(cast(User, request.user), device_id):
            return Response({"detail": "No such device."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SignOutOthersView(APIView):
    throttle_scope = "auth"

    @extend_schema(
        request=None,
        responses={200: SignedOutSerializer},
        summary="Sign out every device but this one",
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        count = devices.end_others(user, keep=request.session.get(devices.SESSION_KEY))
        return Response({"signed_out": count})


def safe_next(value: str | None) -> str:
    """A path on this site to land on after signing in; anything else goes home."""
    if not value or not value.startswith("/") or value.startswith(("//", "/\\")):
        return "/"
    return value


def _to_sign_in(problem: str) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{settings.FRONTEND_URL}/signin?error={problem}")


def _provider(name: str) -> oidc.Provider | None:
    return oidc.google() if name == "google" else None


class OidcStartView(APIView):
    permission_classes = (AllowAny,)
    throttle_scope = "auth"

    @extend_schema(
        responses={302: None, 404: DetailSerializer}, summary="Go to a provider to sign in"
    )
    def get(self, request: Request, provider: str) -> HttpResponseRedirect | Response:
        chosen = _provider(provider)
        if chosen is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return HttpResponseRedirect(
            oidc.start(request._request, chosen, safe_next(request.query_params.get("next")))
        )


class OidcCallbackView(APIView):
    permission_classes = (AllowAny,)
    throttle_scope = "auth"

    @extend_schema(
        responses={302: None, 404: DetailSerializer},
        summary="Where the provider sends the person back; signs in and goes to the app",
    )
    def get(self, request: Request, provider: str) -> HttpResponseRedirect | Response:
        chosen = _provider(provider)
        if chosen is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        params = request.query_params
        if params.get("error"):
            return _to_sign_in("cancelled")
        try:
            claims, landing = oidc.finish(
                request._request, chosen, params.get("code", ""), params.get("state", "")
            )
            user = external.account_for(chosen.key, claims)
        except oidc.Refused:
            return _to_sign_in("failed")
        except external.NotAllowed as refused:
            return _to_sign_in(refused.reason)
        # The provider ran its own checks, so Baithak's two-step code is not asked here.
        lockout.record_success(user)
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        return HttpResponseRedirect(f"{settings.FRONTEND_URL}{landing}")
