from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("csrf/", views.CsrfView.as_view(), name="csrf"),
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("signin/", views.SignInView.as_view(), name="signin"),
    path("signout/", views.SignOutView.as_view(), name="signout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path(
        "verify-email/resend/", views.ResendVerificationView.as_view(), name="verify-email-resend"
    ),
    path("password-reset/", views.PasswordResetView.as_view(), name="password-reset"),
    path(
        "password-reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]
