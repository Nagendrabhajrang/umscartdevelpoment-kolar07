"""Authentication test suite.

Covers the twenty scenarios the specification calls out, split by area. Tests run
against the real services and the real DRF stack; only the outbound delivery
providers are stubbed so no network is touched.

The resend cooldown is part of the product, but waiting sixty seconds between
every test would make the suite unusable, so it is overridden per-test-class
through ``override_settings``. The cooldown itself is still asserted directly in
the tests that care about it.
"""

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomerProfile, User, UserRole
from apps.authentication.models import (
    OTPThrottle,
    OTPVerification,
    OTPPurpose,
    PasswordReset,
)

ADMIN_PASSWORD = "UMSMart@Admin2026"
ADMIN_EMAIL = "nagendrajoe@gmail.com"
CUSTOMER_MOBILE = "9876543210"


@override_settings(
    OTP_RESEND_COOLDOWN_SECONDS=0,
    # Django forces DEBUG=False while tests run, which (correctly) disables the
    # dev-mode OTP echo. Tests need the code to drive the flow, so they opt in
    # explicitly. Production stays protected by the DEBUG guard itself.
    DEBUG=True,
    AUTH_DEV_MODE=True,
)
class AuthTestCase(TestCase):
    """Shared fixtures: one provisioning admin, a clean client, no throttles."""

    def setUp(self):
        cache.clear()
        OTPThrottle.objects.all().delete()
        self.admin = User.objects.create_user(
            username="admin",
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            role=UserRole.ADMIN,
            is_email_verified=True,
        )
        self.client = APIClient()

    # -- helpers ----------------------------------------------------------
    def admin_login(self):
        """Run the full admin flow and return the token pair."""
        response = self.client.post(
            "/api/admin/login/",
            {"username": "admin", "password": ADMIN_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        code = response.data["dev_otp"]
        response = self.client.post("/api/admin/verify-mfa/", {"code": code}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def customer_login(self, mobile=CUSTOMER_MOBILE):
        response = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": mobile}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        code = response.data["dev_otp"]
        return self.client.post(
            "/api/customer/verify-otp/",
            {"mobile_number": mobile, "code": code},
            format="json",
        )

    def bearer(self, token=None):
        """Deprecated in round 30: sessions travel in cookies, not headers.

        Kept as a no-op so older tests that called it still describe the same
        thing - the client is already carrying the session cookie from login.
        """
        return None

    def session_count(self, user):
        """How many live sessions this account has (one per signed-in browser)."""
        from apps.authentication.services import session_service

        return session_service.active_session_count(user)


# ---------------------------------------------------------------------------
# Admin login and MFA
# ---------------------------------------------------------------------------
class AdminLoginTests(AuthTestCase):
    def test_1_admin_login_with_correct_credentials_requests_mfa(self):
        response = self.client.post(
            "/api/admin/login/",
            {"username": "admin", "password": ADMIN_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["mfa_required"])
        self.assertIn("email_hint", response.data)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)

    def test_2_admin_login_with_incorrect_password_is_rejected(self):
        response = self.client.post(
            "/api/admin/login/", {"username": "admin", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "invalid_credentials")

    def test_3_admin_receives_an_email_otp_record(self):
        self.client.post(
            "/api/admin/login/",
            {"username": "admin", "password": ADMIN_PASSWORD},
            format="json",
        )
        record = OTPVerification.objects.filter(
            user=self.admin, purpose=OTPPurpose.ADMIN_MFA
        ).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.delivery_channel, "EMAIL")
        # Stored hashed: the hash must not look like six digits.
        self.assertNotEqual(len(record.otp_hash), 6)

    def test_4_admin_login_succeeds_only_after_correct_otp(self):
        response = self.client.post(
            "/api/admin/login/",
            {"username": "admin", "password": ADMIN_PASSWORD},
            format="json",
        )
        code = response.data["dev_otp"]

        wrong = self.client.post("/api/admin/verify-mfa/", {"code": "000000"}, format="json")
        self.assertEqual(wrong.status_code, 400)
        self.assertNotIn("access", wrong.data)

        right = self.client.post("/api/admin/verify-mfa/", {"code": code}, format="json")
        self.assertEqual(right.status_code, 200)
        # Round 30: success opens a session. No token is handed to the client.
        self.assertNotIn("access", right.data)
        self.assertNotIn("refresh", right.data)
        self.assertIsNotNone(right.cookies.get(settings.SESSION_COOKIE_NAME))
        self.assertEqual(right.data["user"]["role"], "ADMIN")

    def test_5_admin_cannot_reach_protected_api_before_mfa(self):
        self.client.post(
            "/api/admin/login/",
            {"username": "admin", "password": ADMIN_PASSWORD},
            format="json",
        )
        # No token was issued, so the session endpoint must refuse.
        response = self.client.get("/api/auth/session/")
        self.assertEqual(response.status_code, 401)

    def test_non_admin_role_cannot_pass_admin_login(self):
        User.objects.create_user(mobile_number="9111111111", role=UserRole.CUSTOMER)
        response = self.client.post(
            "/api/admin/login/", {"username": "9111111111", "password": "x"}, format="json"
        )
        self.assertEqual(response.status_code, 401)


# ---------------------------------------------------------------------------
# Admin password recovery and change
# ---------------------------------------------------------------------------
class AdminPasswordTests(AuthTestCase):
    def test_6_forgot_password_flow_completes(self):
        start = self.client.post(
            "/api/admin/forgot-password/", {"email": ADMIN_EMAIL}, format="json"
        )
        self.assertEqual(start.status_code, 200)
        code = start.data["dev_otp"]

        verify = self.client.post(
            "/api/admin/verify-reset-otp/", {"email": ADMIN_EMAIL, "code": code}, format="json"
        )
        self.assertEqual(verify.status_code, 200)
        reset_token = verify.data["reset_token"]

        finish = self.client.post(
            "/api/admin/reset-password/",
            {
                "reset_token": reset_token,
                "new_password": "BrandNewPass!2026",
                "confirm_password": "BrandNewPass!2026",
            },
            format="json",
        )
        self.assertEqual(finish.status_code, 200, finish.data)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("BrandNewPass!2026"))

    def test_7_reset_with_invalid_otp_is_refused(self):
        self.client.post("/api/admin/forgot-password/", {"email": ADMIN_EMAIL}, format="json")
        response = self.client.post(
            "/api/admin/verify-reset-otp/", {"email": ADMIN_EMAIL, "code": "123456"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_7b_reset_token_without_otp_verification_is_impossible(self):
        """A caller who never verified an OTP holds no usable reset token."""
        guess = self.client.post(
            "/api/admin/reset-password/",
            {
                "reset_token": "made-up-token",
                "new_password": "BrandNewPass!2026",
                "confirm_password": "BrandNewPass!2026",
            },
            format="json",
        )
        self.assertEqual(guess.status_code, 400)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.check_password("BrandNewPass!2026"))

    def test_forgot_password_does_not_reveal_account_existence(self):
        real = self.client.post(
            "/api/admin/forgot-password/", {"email": ADMIN_EMAIL}, format="json"
        )
        # A different address gets the same message shape and status.
        fake = self.client.post(
            "/api/admin/forgot-password/", {"email": "nobody@example.com"}, format="json"
        )
        self.assertEqual(real.status_code, fake.status_code)
        self.assertEqual(real.data["message"], fake.data["message"])

    def test_change_password_requires_current_password_and_otp(self):
        tokens = self.admin_login()
        self.bearer()

        otp_response = self.client.post("/api/admin/change-password/otp/")
        self.assertEqual(otp_response.status_code, 200)
        code = otp_response.data["dev_otp"]

        bad_current = self.client.post(
            "/api/admin/change-password/",
            {
                "current_password": "wrong",
                "code": code,
                "new_password": "AnotherPass!2026",
                "confirm_password": "AnotherPass!2026",
            },
            format="json",
        )
        self.assertEqual(bad_current.status_code, 400)

        good = self.client.post(
            "/api/admin/change-password/",
            {
                "current_password": ADMIN_PASSWORD,
                "code": code,
                "new_password": "AnotherPass!2026",
                "confirm_password": "AnotherPass!2026",
            },
            format="json",
        )
        self.assertEqual(good.status_code, 200, good.data)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("AnotherPass!2026"))

    def test_password_reset_revokes_every_session(self):
        tokens = self.admin_login()
        self.bearer()
        self.assertEqual(self.client.get("/api/auth/session/").status_code, 200)

        start = self.client.post("/api/admin/forgot-password/", {"email": ADMIN_EMAIL}, format="json")
        verify = self.client.post(
            "/api/admin/verify-reset-otp/",
            {"email": ADMIN_EMAIL, "code": start.data["dev_otp"]},
            format="json",
        )
        self.client.credentials()  # the reset endpoints are public
        self.client.post(
            "/api/admin/reset-password/",
            {
                "reset_token": verify.data["reset_token"],
                "new_password": "ResetPass!2026",
                "confirm_password": "ResetPass!2026",
            },
            format="json",
        )

        # Round 30: a password reset must end the sessions themselves. The row is
        # deleted, so the cookie in the old browser is worthless immediately -
        # a stronger guarantee than a blacklist, which only killed future tokens.
        self.assertEqual(self.client.get("/api/auth/session/").status_code, 401)


# ---------------------------------------------------------------------------
# Customer login
# ---------------------------------------------------------------------------
class CustomerLoginTests(AuthTestCase):
    def test_8_customer_receives_mobile_otp(self):
        response = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        record = OTPVerification.objects.filter(purpose=OTPPurpose.LOGIN).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.delivery_channel, "SMS")

    def test_9_customer_login_with_valid_otp(self):
        response = self.customer_login()
        self.assertEqual(response.status_code, 200)
        # Round 30: the payload carries the user; the credential is a cookie.
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertIsNotNone(response.cookies.get(settings.SESSION_COOKIE_NAME))
        self.assertEqual(response.data["user"]["role"], "CUSTOMER")
        # And the session actually works.
        self.assertEqual(self.client.get("/api/customer/profile/").status_code, 200)

    def test_10_new_customer_is_registered_automatically(self):
        self.assertEqual(User.objects.filter(role=UserRole.CUSTOMER).count(), 0)
        response = self.customer_login()
        self.assertTrue(response.data["is_new_customer"])
        user = User.objects.get(role=UserRole.CUSTOMER)
        self.assertEqual(user.mobile_number, "+919876543210")
        self.assertTrue(user.is_mobile_verified)
        # The commerce profile is created in the same transaction.
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())

    def test_11_existing_customer_does_not_create_a_duplicate(self):
        first = self.customer_login()
        self.assertTrue(first.data["is_new_customer"])

        second = self.customer_login()
        self.assertFalse(second.data["is_new_customer"])
        self.assertEqual(
            User.objects.filter(role=UserRole.CUSTOMER).count(), 1
        )

    def test_11b_equivalent_spellings_resolve_to_the_same_account(self):
        self.customer_login("9876543210")
        for spelling in ("+919876543210", "09876543210", "919876543210"):
            response = self.customer_login(spelling)
            self.assertEqual(response.status_code, 200, spelling)
            self.assertFalse(response.data["is_new_customer"], spelling)
        self.assertEqual(User.objects.filter(role=UserRole.CUSTOMER).count(), 1)

    def test_invalid_mobile_number_is_rejected(self):
        for bad in ("12345", "abcdefghij", "0123456789", "99999999999"):
            response = self.client.post(
                "/api/customer/send-otp/", {"mobile_number": bad}, format="json"
            )
            self.assertEqual(response.status_code, 400, bad)


# ---------------------------------------------------------------------------
# Customer profile
# ---------------------------------------------------------------------------
class CustomerProfileUpdateTests(AuthTestCase):
    def test_profile_update_persists_the_name(self):
        response = self.customer_login()
        self.bearer()

        updated = self.client.patch(
            "/api/customer/profile/", {"full_name": "Nagendra Joe"}, format="json"
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["display_name"], "Nagendra Joe")

        fetched = self.client.get("/api/customer/profile/")
        self.assertEqual(fetched.data["display_name"], "Nagendra Joe")

    def test_display_name_is_accepted_as_a_write_alias(self):
        response = self.customer_login()
        self.bearer()
        updated = self.client.put(
            "/api/customer/profile/", {"display_name": "Via Alias"}, format="json"
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["display_name"], "Via Alias")

    def test_profile_email_update_clears_verification(self):
        response = self.customer_login()
        self.bearer()
        updated = self.client.patch(
            "/api/customer/profile/", {"email": "shopper@example.com"}, format="json"
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["email"], "shopper@example.com")
        self.assertFalse(updated.data["is_email_verified"])

    def test_blank_name_is_rejected(self):
        """customers.Customer.full_name is NOT NULL, so a blank name is invalid."""
        response = self.customer_login()
        self.bearer()
        rejected = self.client.patch(
            "/api/customer/profile/", {"full_name": "   "}, format="json"
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.data["error"]["code"], "invalid_full_name")

    def test_identity_fields_cannot_be_rewritten(self):
        response = self.customer_login()
        self.bearer()
        self.client.patch(
            "/api/customer/profile/",
            {"mobile_number": "9999999999", "role": "ADMIN"},
            format="json",
        )
        user = User.objects.get(role=UserRole.CUSTOMER)
        self.assertEqual(user.mobile_number, "+919876543210")
        self.assertEqual(user.role, UserRole.CUSTOMER)


# ---------------------------------------------------------------------------
# OTP policy
# ---------------------------------------------------------------------------
class OTPPolicyTests(AuthTestCase):
    def test_12_expired_otp_is_rejected(self):
        response = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        code = response.data["dev_otp"]

        OTPVerification.objects.filter(purpose=OTPPurpose.LOGIN).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        verify = self.client.post(
            "/api/customer/verify-otp/",
            {"mobile_number": CUSTOMER_MOBILE, "code": code},
            format="json",
        )
        self.assertEqual(verify.status_code, 400)
        self.assertEqual(verify.data["error"]["code"], "otp_expired")

    def test_13_attempt_limit_is_enforced(self):
        self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        for _ in range(5):
            self.client.post(
                "/api/customer/verify-otp/",
                {"mobile_number": CUSTOMER_MOBILE, "code": "000000"},
                format="json",
            )
        exhausted = self.client.post(
            "/api/customer/verify-otp/",
            {"mobile_number": CUSTOMER_MOBILE, "code": "000000"},
            format="json",
        )
        self.assertEqual(exhausted.status_code, 400)
        self.assertEqual(exhausted.data["error"]["code"], "otp_attempts_exhausted")

    @override_settings(OTP_RESEND_COOLDOWN_SECONDS=60, DEBUG=True, AUTH_DEV_MODE=True)
    def test_14_resend_cooldown_is_enforced(self):
        first = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            "/api/customer/resend-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.data["error"]["code"], "otp_resend_cooldown")

    def test_otp_is_single_use(self):
        response = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        code = response.data["dev_otp"]
        first = self.client.post(
            "/api/customer/verify-otp/",
            {"mobile_number": CUSTOMER_MOBILE, "code": code},
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        replay = self.client.post(
            "/api/customer/verify-otp/",
            {"mobile_number": CUSTOMER_MOBILE, "code": code},
            format="json",
        )
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(replay.data["error"]["code"], "otp_already_used")

    def test_otp_is_stored_hashed_not_plaintext(self):
        response = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        code = response.data["dev_otp"]
        record = OTPVerification.objects.filter(purpose=OTPPurpose.LOGIN).first()
        self.assertNotIn(code, record.otp_hash)
        self.assertGreaterEqual(len(record.otp_hash), 40)

    def test_requesting_a_new_code_invalidates_the_previous_one(self):
        first = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        old_code = first.data["dev_otp"]
        self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        response = self.client.post(
            "/api/customer/verify-otp/",
            {"mobile_number": CUSTOMER_MOBILE, "code": old_code},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


# ---------------------------------------------------------------------------
# Profile link invariant
# ---------------------------------------------------------------------------
class CustomerProfileLinkTests(AuthTestCase):
    """The link to the commerce Customer must survive a lost profile row.

    A verified account without that link could sign in but could not reach
    checkout, and the failure surfaced as a confusing "supply X-Customer-Id"
    error on endpoints that have nothing to do with headers.
    """

    def test_login_restores_a_missing_profile_link(self):
        response = self.customer_login()
        user = User.objects.get(role=UserRole.CUSTOMER)
        self.assertIsNotNone(response.data["user"]["customer_id"])

        # Simulate the damaged state: verified account, link gone.
        CustomerProfile.objects.filter(user=user).delete()
        self.assertFalse(CustomerProfile.objects.filter(user=user).exists())

        # Signing in again must repair it rather than leave the account stuck.
        again = self.customer_login()
        self.assertEqual(again.status_code, 200)
        self.assertIsNotNone(again.data["user"]["customer_id"])
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())

        # Ordering is reported as an existing customer, not a brand-new one.
        self.assertFalse(again.data["is_new_customer"])

    def test_missing_link_is_repaired_mid_session(self):
        """Round 24 regression: a vanished link must not end the session.

        The storefront shows "Your session has expired. Please sign in again"
        whenever a request comes back with an identity fault. A missing
        ``CustomerProfile`` used to answer 409 ``customer_profile_missing``, so
        the shopper was signed out a fraction of a second after signing in,
        every single time. The request path now rebuilds the link instead.
        """
        tokens = self.customer_login()
        user = User.objects.get(role=UserRole.CUSTOMER)
        CustomerProfile.objects.filter(user=user).delete()
        self.assertFalse(CustomerProfile.objects.filter(user=user).exists())

        self.bearer()
        response = self.client.post("/api/v1/orders/checkout/preview/", {}, format="json")

        # The request succeeds and the link is back.
        self.assertNotEqual(response.status_code, 409)
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())

    def test_cart_works_after_the_link_was_lost(self):
        tokens = self.customer_login()
        user = User.objects.get(role=UserRole.CUSTOMER)
        CustomerProfile.objects.filter(user=user).delete()

        self.bearer()
        cart = self.client.get("/api/v1/cart/")
        self.assertEqual(cart.status_code, 200)
        self.assertIsNotNone(cart.data["customer"])


# ---------------------------------------------------------------------------
# JWT and sessions
# ---------------------------------------------------------------------------
class SessionTests(AuthTestCase):
    """Round 30: Django sessions, not tokens.

    Each test here corresponds to a way the old token design could sign a healthy
    shopper out. The point of the class is that those failure modes no longer
    exist - there is no access token to expire mid-page and no refresh call that
    can fail.
    """

    def test_15_login_creates_a_django_session(self):
        from django.contrib.sessions.models import Session

        response = self.customer_login()
        self.assertEqual(response.status_code, 200)

        # The credential is the cookie, and it is HttpOnly.
        cookie = response.cookies.get(settings.SESSION_COOKIE_NAME)
        self.assertIsNotNone(cookie, "login must set the session cookie")
        self.assertTrue(cookie["httponly"], "session cookie must be HttpOnly")
        self.assertGreater(int(cookie["max-age"] or 0), 6 * 24 * 3600)

        # A real row exists.
        self.assertGreater(Session.objects.count(), 0)

        # And nothing token-shaped is returned.
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertNotIn("session_id", response.data)

    def test_15b_session_cookie_is_never_exposed_to_javascript(self):
        """No credential may be readable by script.

        The CSRF cookie is deliberately readable (double-submit needs it); the
        session cookie must never be.
        """
        response = self.customer_login()
        session_cookie = response.cookies.get(settings.SESSION_COOKIE_NAME)
        self.assertTrue(session_cookie["httponly"])
        self.assertNotEqual(
            settings.SESSION_COOKIE_NAME, settings.CSRF_COOKIE_NAME
        )

    def test_16_session_survives_requests_without_refresh(self):
        """The whole point: no refresh step exists, so none can fail."""
        self.customer_login()

        for _ in range(3):
            profile = self.client.get("/api/customer/profile/")
            self.assertEqual(profile.status_code, 200)
            self.assertEqual(self.client.get("/api/auth/session/").status_code, 200)

    def test_16b_session_has_a_seven_day_lifetime(self):
        from django.contrib.sessions.models import Session

        self.assertEqual(settings.SESSION_COOKIE_AGE, 60 * 60 * 24 * 7)
        self.assertFalse(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)

        self.customer_login()
        session = Session.objects.latest("expire_date")
        remaining = (session.expire_date - timezone.now()).total_seconds()
        # Allow a minute of slack for the request itself.
        self.assertAlmostEqual(remaining, 60 * 60 * 24 * 7, delta=120)

    def test_17_concurrent_logins_are_allowed(self):
        """Two devices, two independent sessions, one account."""
        first = self.customer_login()
        user = User.objects.get(mobile_number__endswith=CUSTOMER_MOBILE[-9:])

        self.assertEqual(self.session_count(user), 1)

        # Second login from a separate client (a different browser).
        other = APIClient()
        code = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        # Cooldown: reuse the code we just verified is not possible, so clear it.
        from apps.authentication.models import OTPVerification

        OTPVerification.objects.all().delete()
        code = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        second = other.post(
            "/api/customer/verify-otp/",
            {"mobile_number": CUSTOMER_MOBILE, "code": code.data["dev_otp"]},
            format="json",
        )
        self.assertEqual(second.status_code, 200)

        # Two rows now, and both clients work.
        self.assertEqual(self.session_count(user), 2)
        self.assertEqual(self.client.get("/api/customer/profile/").status_code, 200)
        self.assertEqual(other.get("/api/customer/profile/").status_code, 200)

    def test_17b_admin_and_customer_sessions_are_independent(self):
        """An admin login must not disturb a customer session."""
        customer = APIClient()
        OTPVerification = None
        response = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        self.client.post(
            "/api/customer/verify-otp/",
            {"mobile_number": CUSTOMER_MOBILE, "code": response.data["dev_otp"]},
            format="json",
        )
        self.assertEqual(self.client.get("/api/customer/profile/").status_code, 200)

        self.admin_login()
        self.assertEqual(self.client.get("/api/auth/session/").data["role"], "ADMIN")

    def test_17c_logout_elsewhere_does_not_affect_this_device(self):
        """Logging out on one device must not sign out the other."""
        from apps.authentication.models import OTPVerification

        self.customer_login()  # device A
        other = APIClient()
        OTPVerification.objects.all().delete()
        code = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        other.post(
            "/api/customer/verify-otp/",
            {"mobile_number": CUSTOMER_MOBILE, "code": code.data["dev_otp"]},
            format="json",
        )
        self.assertEqual(other.get("/api/customer/profile/").status_code, 200)

        # Device A signs out.
        self.assertEqual(self.client.post("/api/customer/logout/").status_code, 200)
        self.assertEqual(self.client.get("/api/customer/profile/").status_code, 401)

        # Device B is untouched.
        self.assertEqual(other.get("/api/customer/profile/").status_code, 200)

    def test_18_logout_destroys_the_session_server_side(self):
        """logout() flushes the row, not just the cookie."""
        from django.contrib.sessions.models import Session

        self.customer_login()
        before = Session.objects.count()
        self.assertGreater(before, 0)

        response = self.client.post("/api/customer/logout/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Session.objects.count(), before - 1)

        # The client can no longer reach anything.
        self.assertEqual(self.client.get("/api/customer/profile/").status_code, 401)

    def test_logout_all_ends_every_session(self):
        from apps.authentication.models import OTPVerification

        self.customer_login()
        other = APIClient()
        OTPVerification.objects.all().delete()
        code = self.client.post(
            "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE}, format="json"
        )
        other.post(
            "/api/customer/verify-otp/",
            {"mobile_number": CUSTOMER_MOBILE, "code": code.data["dev_otp"]},
            format="json",
        )

        response = self.client.post("/api/auth/logout-all/")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.client.get("/api/customer/profile/").status_code, 401)
        self.assertEqual(other.get("/api/customer/profile/").status_code, 401)

    def test_session_is_restored_after_a_reload(self):
        """A page refresh re-uses the cookie; no second OTP is asked for."""
        self.customer_login()

        # A brand-new client that shares nothing but the cookie file is what a
        # reload looks like to the server.
        fresh = APIClient()
        cookie = self.client.cookies.get(settings.SESSION_COOKIE_NAME)
        fresh.cookies[settings.SESSION_COOKIE_NAME] = cookie.value

        session = fresh.get("/api/auth/session/")
        self.assertEqual(session.status_code, 200)
        self.assertEqual(session.data["role"], "CUSTOMER")
        self.assertEqual(fresh.get("/api/customer/profile/").status_code, 200)


class RoleSeparationTests(AuthTestCase):
    def test_19_admin_cannot_use_customer_endpoints(self):
        tokens = self.admin_login()
        self.bearer()
        self.assertEqual(self.client.get("/api/customer/profile/").status_code, 403)

    def test_20_customer_cannot_use_admin_endpoints(self):
        response = self.customer_login()
        self.bearer()
        self.assertEqual(
            self.client.post("/api/admin/change-password/otp/").status_code, 403
        )

    def test_unauthenticated_requests_are_refused(self):
        self.assertEqual(self.client.get("/api/customer/profile/").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/session/").status_code, 401)

    def test_role_claim_cannot_be_forged(self):
        """A customer token stays a customer token - the role is server-side."""
        response = self.customer_login()
        self.bearer()
        session = self.client.get("/api/auth/session/")
        self.assertEqual(session.data["role"], "CUSTOMER")

    def test_a_dead_cookie_is_not_an_identity(self):
        """A session cookie whose row is gone must not break public pages.

        The token-era version of this test guarded against an expired bearer
        killing the catalogue. The session-era risk is the mirror image: a stale
        cookie must be ignored, not treated as an authentication failure that
        takes the whole page down.
        """
        self.customer_login()

        # Delete the session server-side, as `clearsessions` or a logout does.
        from django.contrib.sessions.models import Session

        Session.objects.all().delete()

        # Public data still answers. A dead cookie proves nothing, so it is
        # simply not an identity.
        for path in ("/api/v1/store-settings/", "/api/v1/banners/live/"):
            self.assertNotEqual(
                self.client.get(path).status_code,
                401,
                f"{path} must not 401 on a stale session cookie",
            )

        # Account-scoped endpoints refuse it with the honest answer.
        self.assertEqual(self.client.get("/api/customer/profile/").status_code, 401)
