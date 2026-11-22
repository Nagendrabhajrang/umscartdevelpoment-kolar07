from django.urls import path

from apps.authentication import views

app_name = "auth_admin"

urlpatterns = [
    path("login/", views.AdminLoginView.as_view(), name="login"),
    path("verify-mfa/", views.AdminVerifyMFAView.as_view(), name="verify-mfa"),
    path("resend-mfa-otp/", views.AdminResendMFAView.as_view(), name="resend-mfa-otp"),
    path("forgot-password/", views.AdminForgotPasswordView.as_view(), name="forgot-password"),
    path("verify-reset-otp/", views.AdminVerifyResetOTPView.as_view(), name="verify-reset-otp"),
    path("reset-password/", views.AdminResetPasswordView.as_view(), name="reset-password"),
    path("change-password/", views.AdminChangePasswordView.as_view(), name="change-password"),
    path("change-password/otp/", views.AdminChangePasswordRequestOTPView.as_view(), name="change-password-otp"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
]
