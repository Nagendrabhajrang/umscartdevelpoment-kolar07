from django.urls import path

from apps.authentication import views

app_name = "auth_customer"

urlpatterns = [
    path("send-otp/", views.CustomerSendOTPView.as_view(), name="send-otp"),
    path("verify-otp/", views.CustomerVerifyOTPView.as_view(), name="verify-otp"),
    path("resend-otp/", views.CustomerResendOTPView.as_view(), name="resend-otp"),
    path("profile/", views.CustomerProfileView.as_view(), name="profile"),
    path("profile/update/", views.CustomerProfileView.as_view(), name="profile-update"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
]
