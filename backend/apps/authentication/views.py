"""Authentication HTTP layer.

Views are thin: parse, delegate to a service, return a JSON envelope. Every
protected view declares an explicit permission class - none of them rely on the
project-wide default.
"""

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.authentication import serializers as s
from apps.authentication.permissions import IsAdminRole, IsCustomerRole
from apps.authentication.services import auth_service, session_service
from apps.authentication.services import otp_service
from common.exceptions import BusinessRuleError, ValidationError

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


#: Round 30: the session cookie IS the credential now. These helpers exist only
#: to make the *old* refresh cookie go away on browsers that still hold one.
LEGACY_REFRESH_COOKIE = "ums_refresh"


def _clear_legacy_refresh_cookie(response):
    """Delete the pre-session refresh cookie, on every path it could be on.

    A browser that was signed in before this round still holds ``ums_refresh``.
    It is inert now - nothing reads it - but it is a live-looking credential in
    the user's cookie jar, so it gets removed at the first opportunity.
    """
    for path in ("/api/", "/api/auth/", "/"):
        response.delete_cookie(LEGACY_REFRESH_COOKIE, path=path, samesite="Lax")
    return response


def _ok(data, status_code=status.HTTP_200_OK):
    """Success envelope. Auth responses must never be cached."""
    return Response(data, status=status_code, headers=NO_STORE)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
class AdminLoginView(APIView):
    """Validate username + password, then send the email OTP.

    Returns a challenge only. No token exists until ``verify-mfa`` succeeds.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=s.AdminLoginSerializer, responses={200: dict})
    def post(self, request):
        serializer = s.AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = auth_service.admin_login_start(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            request=request,
        )
        return _ok(data)


class AdminResendMFAView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        return _ok(auth_service.admin_resend_mfa(request=request))


class AdminVerifyMFAView(APIView):
    """The only place an admin token is minted."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=s.OTPCodeSerializer, responses={200: dict})
    def post(self, request):
        serializer = s.OTPCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = auth_service.admin_verify_mfa(
            code=serializer.validated_data["code"], request=request
        )
        return _clear_legacy_refresh_cookie(_ok(data))


class AdminForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = s.AdminForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _ok(
            auth_service.admin_forgot_password(
                email=serializer.validated_data["email"], request=request
            )
        )


class AdminVerifyResetOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = s.AdminVerifyResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _ok(
            auth_service.admin_verify_reset_otp(
                email=serializer.validated_data["email"],
                code=serializer.validated_data["code"],
                request=request,
            )
        )


class AdminResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = s.AdminResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _ok(
            auth_service.admin_reset_password(
                reset_token=serializer.validated_data["reset_token"],
                new_password=serializer.validated_data["new_password"],
            )
        )


class AdminChangePasswordRequestOTPView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        return _ok(auth_service.admin_change_password_request_otp(user=request.user, request=request))


class AdminChangePasswordView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = s.AdminChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = auth_service.admin_change_password(
            user=request.user,
            current_password=serializer.validated_data["current_password"],
            code=serializer.validated_data["code"],
            new_password=serializer.validated_data["new_password"],
            request=request,
        )
        return _ok(data)


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
class CustomerSendOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=s.MobileSerializer, responses={200: dict})
    def post(self, request):
        serializer = s.MobileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _ok(
            auth_service.customer_send_otp(
                mobile_number=serializer.validated_data["mobile_number"], request=request
            )
        )


class CustomerResendOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = s.MobileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _ok(
            auth_service.customer_resend_otp(
                mobile_number=serializer.validated_data["mobile_number"], request=request
            )
        )


class CustomerVerifyOTPView(APIView):
    """Verify the SMS code; registers the account on first success."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=s.CustomerVerifyOTPSerializer, responses={200: dict})
    def post(self, request):
        serializer = s.CustomerVerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = auth_service.customer_verify_otp(
            mobile_number=serializer.validated_data["mobile_number"],
            code=serializer.validated_data["code"],
            request=request,
        )
        # The Django session cookie is already on the response: login() sets it.
        response = _ok(payload)
        return _clear_legacy_refresh_cookie(response)


class CustomerProfileView(APIView):
    permission_classes = [IsAuthenticated, IsCustomerRole]

    def get(self, request):
        return _ok(auth_service._user_payload(request.user))

    def put(self, request):
        return self._update(request)

    def patch(self, request):
        return self._update(request)

    def _update(self, request):
        serializer = s.CustomerProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        user = request.user
        profile = getattr(user, "customer_profile", None)
        if profile is None:
            raise BusinessRuleError(
                message="No customer profile is linked to this account.",
                code="profile_missing",
            )

        customer = profile.customer
        customer_fields = []
        user_fields = []

        if "full_name" in serializer.validated_data:
            # User.display_name reads this through the profile bridge, so the
            # Customer row is the only place the name needs to live.
            # customers.Customer.full_name is NOT NULL, and that table predates
            # this module, so a blank name is a validation error rather than a
            # schema change on live commerce data.
            name = (serializer.validated_data["full_name"] or "").strip()
            if not name:
                raise BusinessRuleError(
                    message="Name cannot be empty.",
                    code="invalid_full_name",
                )
            customer.full_name = name
            customer_fields.append("full_name")

        if "email" in serializer.validated_data:
            email = serializer.validated_data["email"] or None
            customer.email = email
            customer_fields.append("email")
            user.email = email
            user_fields.append("email")
            # Changing the address invalidates a previous verification.
            if user.is_email_verified:
                user.is_email_verified = False
                user_fields.append("is_email_verified")

        if customer_fields:
            customer.save(update_fields=customer_fields)
        if user_fields:
            user.save(update_fields=user_fields)

        return _ok(auth_service._user_payload(user))


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------
class SessionView(APIView):
    """Who is signed in, straight from the Django session.

    This is the endpoint a page load calls. A 200 means "still signed in"; a 401
    means the server has positively confirmed there is no valid session, and only
    then may the client redirect to the login screen.

    Round 30 note: this never refreshes anything, because there is nothing to
    refresh. Either the session row exists or it does not.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        info = session_service.session_payload(request)
        return _ok(
            {
                "authenticated": True,
                "role": user.role,
                "user_id": user.pk,
                "user": {
                    **auth_service._user_payload(user),
                    "is_admin": user.role == UserRole.ADMIN,
                    "is_customer": user.role == UserRole.CUSTOMER,
                },
                **info,
            }
        )


SessionViewWithoutAuth = SessionView


class SessionStatusView(APIView):
    """Anonymous-safe session probe.

    ``/api/auth/session/`` answering 401 is the documented contract, but a client
    bootstrapping on a public page benefits from a positive "no session" answer it
    can branch on without treating an error as a failure. Same information, always
    200.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django.contrib.auth import get_user

        user = get_user(request)
        if not (user and user.is_authenticated):
            return _ok({"authenticated": False, "role": None, "user": None})
        return _ok(
            {
                "authenticated": True,
                "role": getattr(user, "role", None),
                "user_id": user.pk,
                "user": auth_service._user_payload(user),
            }
        )


class LogoutView(APIView):
    """End *this browser's* session.

    ``logout()`` flushes the session server-side and clears the cookie, so the
    session id cannot be replayed. Other browsers signed into the same account
    are deliberately untouched - a shopper closing the site on a laptop must not
    be thrown off their phone.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_service.end_session(request)
        response = _ok({"message": "Signed out."})
        return _clear_legacy_refresh_cookie(response)


class LogoutAllView(APIView):
    """End every session for this account: the explicit "sign out everywhere"."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        count = session_service.blacklist_all_for_user(user)
        session_service.end_session(request)
        response = _ok(
            {"message": "Signed out of all devices.", "sessions_revoked": count}
        )
        return _clear_legacy_refresh_cookie(response)


class CSRFView(APIView):
    """Hand the browser a CSRF token and make sure it is stored in a cookie.

    WHY THIS IS NEEDED
    ------------------
    With session authentication every unsafe request (POST/PATCH/DELETE) must
    carry ``X-CSRFToken`` and the browser must hold the ``csrftoken`` cookie.
    Django normally plants that cookie when it renders a template with
    ``{% csrf_token %}`` - and a single-page app never receives one.

    So the storefront and the dashboard call this endpoint on boot. ``get_token``
    puts the secret in ``request.META`` and ``ensure_csrf_cookie`` makes Django
    write the cookie on this response. The client then echoes the value from the
    cookie into the header.

    This leaks nothing: the CSRF token is not a credential on its own. It is only
    meaningful paired with the session cookie, which JavaScript cannot read.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django.middleware.csrf import get_token
        from django.utils.decorators import method_decorator
        from django.views.decorators.csrf import ensure_csrf_cookie

        token = get_token(request)
        response = _ok({"csrf_token": token})
        response.set_cookie(
            settings.CSRF_COOKIE_NAME,
            token,
            max_age=int(settings.SESSION_COOKIE_AGE),
            httponly=False,          # the SPA must read it
            secure=settings.CSRF_COOKIE_SECURE,
            samesite=settings.CSRF_COOKIE_SAMESITE,
            path="/",
        )
        return response
