from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("csrf/", views.CsrfView.as_view(), name="csrf"),
    path("config/", views.AuthConfigView.as_view(), name="config"),
    path("signup/", views.SignUpView.as_view(), name="signup"),
    path("signin/", views.SignInView.as_view(), name="signin"),
    path("signin/two-step/", views.SignInTwoStepView.as_view(), name="signin-two-step"),
    path("two-step/", views.TwoStepView.as_view(), name="two-step"),
    path("two-step/setup/", views.TwoStepSetupView.as_view(), name="two-step-setup"),
    path("two-step/enable/", views.TwoStepEnableView.as_view(), name="two-step-enable"),
    path("two-step/disable/", views.TwoStepDisableView.as_view(), name="two-step-disable"),
    path("two-step/recovery-codes/", views.RecoveryCodesView.as_view(), name="two-step-recovery"),
    path("signout/", views.SignOutView.as_view(), name="signout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("delete-account/", views.DeleteAccountView.as_view(), name="delete-account"),
    path("notifications/", views.NotificationSettingsView.as_view(), name="notifications"),
    path("availability/", views.AvailabilityView.as_view(), name="availability"),
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
