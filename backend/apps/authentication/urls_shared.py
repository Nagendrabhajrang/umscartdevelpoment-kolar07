from django.urls import path

from apps.authentication import views

app_name = "auth_shared"

urlpatterns = [
    # Round 30: the session is the credential. `/api/auth/session/` is the check
    # a page load makes; 200 means signed in, 401 means the server confirmed the
    # session is gone and the client may redirect to login.
    # Bootstraps the CSRF cookie the SPA needs before any unsafe request.
    path("csrf/", views.CSRFView.as_view(), name="csrf"),
    path("session/", views.SessionView.as_view(), name="session"),
    # Always-200 variant for bootstrapping on public pages.
    path("session/status/", views.SessionStatusView.as_view(), name="session-status"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("logout-all/", views.LogoutAllView.as_view(), name="logout-all"),
]
