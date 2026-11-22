#!/usr/bin/env python3
"""End-to-end check of the authentication API against a running server.

Unlike the Django suite (which uses the test database), this drives the real
stack over HTTP and inspects the live PostgreSQL state. Run it after starting
the server:

    python3 manage.py runserver 0.0.0.0:8000 --noreload
    python3 scripts/e2e_auth_check.py

Exit code is 0 only when every check passes.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")
ADMIN_USERNAME = os.environ.get("E2E_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD", "UMSMart@Admin2026")
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL", "nagendrajoe@gmail.com")
MOBILE = "9876543210"

PG = {
    "env": {**os.environ, "PGPASSWORD": os.environ.get("DB_PASSWORD", "1234")},
    "db": os.environ.get("DB_NAME", "ums_mart_db"),
    "user": os.environ.get("DB_USER", "ums_mart_user"),
}

_passed = 0
_failed = 0


class Browser:
    """A cookie jar that behaves like one browser.

    Round 30: the session is a cookie, so "who is calling" is no longer an
    argument to a function - it is which jar the request is sent through. Each
    `Browser()` is an independent device.
    """

    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar)
        )

    # -- cookies -------------------------------------------------------
    def cookie(self, name):
        for c in self.jar:
            if c.name == name:
                return c.value
        return None

    @property
    def csrf(self):
        return self.cookie("ums_mart_csrftoken")

    def bootstrap_csrf(self):
        if not self.csrf:
            self.call("GET", "/api/auth/csrf/")
        return self.csrf

    # -- requests ------------------------------------------------------
    def call(self, method, path, body=None, headers=None):
        """Perform one request through this browser's cookie jar.

        Unsafe methods carry the CSRF header automatically, exactly as the React
        client does - without it Django refuses them, which is the point.
        """
        payload = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(BASE + path, data=payload, method=method)
        request.add_header("Content-Type", "application/json")
        request.add_header("Accept", "application/json")

        if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            token = self.bootstrap_csrf()
            if token:
                request.add_header("X-CSRFToken", token)

        for key, value in (headers or {}).items():
            request.add_header(key, value)

        try:
            with self.opener.open(request, timeout=20) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as error:
            raw = error.read()
            try:
                return error.code, (json.loads(raw) if raw else {})
            except json.JSONDecodeError:
                return error.code, {"raw": raw[:200].decode(errors="replace")}


#: The default browser used by the checks. Sections that need two devices make
#: their own.
BROWSER = Browser()


def call(method, path, body=None, browser=None):
    return (browser or BROWSER).call(method, path, body)


def _clone_cookie(browser, name):
    """A copy of one cookie, for simulating a second browser tab."""
    for cookie in browser.jar:
        if cookie.name == name:
            return http.cookiejar.Cookie(
                version=cookie.version,
                name=cookie.name,
                value=cookie.value,
                port=cookie.port,
                port_specified=cookie.port_specified,
                domain=cookie.domain,
                domain_specified=cookie.domain_specified,
                domain_initial_dot=cookie.domain_initial_dot,
                path=cookie.path,
                path_specified=cookie.path_specified,
                secure=cookie.secure,
                expires=cookie.expires,
                discard=cookie.discard,
                comment=cookie.comment,
                comment_url=cookie.comment_url,
                rest=cookie._rest,
            )
    raise AssertionError(f"cookie {name} not found - is anything signed in?")


def _reload(browser):
    """A new jar holding only the session cookie: exactly what a reload sends.

    A page refresh keeps the cookies and throws away everything in memory, so
    this is the honest simulation of "did the session survive F5".
    """
    fresh = Browser()
    fresh.jar.set_cookie(_clone_cookie(browser, "ums_mart_sessionid"))
    return fresh


def admin_login_mfa_code(browser):
    """Run the password step on ``browser`` and return its MFA code.

    Codes are stored hashed, so the only way to get one is the response that
    issues it - which is exactly how a real admin gets theirs (by email).
    """
    clear_otp_state()
    status, body = browser.call(
        "POST", "/api/admin/login/",
        {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    code = body.get("dev_otp")
    if not code:
        raise AssertionError(f"no dev_otp in the login response ({status}): {body}")
    return code


def sql(statement):
    """Run a housekeeping statement so cooldowns don't block consecutive runs."""
    subprocess.run(
        ["psql", "-h", "localhost", "-U", PG["user"], "-d", PG["db"], "-q", "-c", statement],
        env=PG["env"],
        capture_output=True,
    )


def check(label, condition, detail=""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}   {detail}")


def section(title):
    print(f"\n=== {title} ===")


def clear_otp_state():
    """Clear the OTP tables so the 60 s resend cooldown doesn't block the run.

    The cooldown is derived from the most recent OTPVerification row, not from
    the throttle table, so both have to go. Sessions and tokens are untouched:
    previously issued tokens stay valid, which is what the session checks need.
    """
    sql("DELETE FROM auth_otp_throttle;DELETE FROM auth_otp_verification;")


def reset_auth_state():
    """Clear every auth table between phases, leaving commerce data alone."""
    sql(
        "DELETE FROM django_session;"
        "DELETE FROM auth_otp_throttle;"
        "DELETE FROM auth_otp_verification;"
    )


def main():
    section("0. Server reachable")
    try:
        status, _ = call("GET", "/api/auth/session/")
        check("server responds", status in (401, 403), status)
    except Exception as exc:  # noqa: BLE001 - report and stop
        print(f"  FAIL  cannot reach {BASE}: {exc}")
        return 1

    reset_auth_state()

    section("1. Admin login: password issues an MFA challenge, not tokens")
    status, body = call(
        "POST", "/api/admin/login/", {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
    )
    check("200 OK", status == 200, body)
    check("mfa_required", body.get("mfa_required") is True, body)
    check("no access token yet", "access" not in body, body)
    check("no refresh token yet", "refresh" not in body, body)
    check("email hint is masked", "*" in str(body.get("email_hint", "")), body.get("email_hint"))
    admin_code = body.get("dev_otp")
    check("dev_otp delivered", bool(admin_code), body)

    section("2. Wrong password is rejected")
    status, body = call(
        "POST", "/api/admin/login/", {"username": ADMIN_USERNAME, "password": "not-the-password"}
    )
    check("401", status == 401, body)
    check("code invalid_credentials", body.get("error", {}).get("code") == "invalid_credentials", body)

    section("3. Wrong MFA code is rejected without leaking a token")
    status, body = call("POST", "/api/admin/verify-mfa/", {"code": "000000"})
    check("400", status == 400, body)
    check("no token", "access" not in body and "refresh" not in body, body)

    section("4. Correct MFA code opens an admin session")
    status, body = call("POST", "/api/admin/verify-mfa/", {"code": admin_code})
    check("200", status == 200, body)
    check("role ADMIN", body.get("user", {}).get("role") == "ADMIN", body.get("user"))
    # Round 30: no tokens. The credential is an HttpOnly cookie.
    check("no access token in body", "access" not in body, list(body))
    check("no refresh token in body", "refresh" not in body, list(body))
    check("session cookie set", bool(BROWSER.cookie("ums_mart_sessionid")))

    section("5. An OTP cannot be replayed")
    status, body = call("POST", "/api/admin/verify-mfa/", {"code": admin_code})
    check("replay refused", status == 400, body)
    check("code otp_already_used", body.get("error", {}).get("code") == "otp_already_used", body)

    section("6. The admin session is live")
    status, body = call("GET", "/api/auth/session/")
    check("200", status == 200, body)
    check("authenticated", body.get("authenticated") is True, body)
    check("role ADMIN", body.get("role") == "ADMIN", body)

    section("7. Customer OTP is sent to a mobile number")
    status, body = call("POST", "/api/customer/send-otp/", {"mobile_number": MOBILE})
    check("200", status == 200, body)
    customer_code = body.get("dev_otp")
    check("dev_otp delivered", bool(customer_code), body)
    check("mobile hint masked", "X" in str(body.get("mobile_hint", "")), body.get("mobile_hint"))

    section("8. First customer login auto-registers")
    status, body = call(
        "POST", "/api/customer/verify-otp/", {"mobile_number": MOBILE, "code": customer_code}
    )
    check("200", status == 200, body)
    check(
        "session opened (cookie)",
        bool(BROWSER.cookie("ums_mart_sessionid")),
        "no ums_mart_sessionid cookie",
    )
    check("role CUSTOMER", body.get("user", {}).get("role") == "CUSTOMER", body.get("user"))
    # Round 23: this run reuses the demo number, which may already exist from an
    # earlier suite. What matters is that verification succeeds and issues
    # tokens; "new vs returning" is asserted in section 11 below.
    check("verify-otp issued a session", bool(BROWSER.cookie("ums_mart_sessionid")), body.get("is_new_customer"))
    check(
        "mobile stored in canonical form",
        body.get("user", {}).get("mobile_number") == "+91" + MOBILE,
        body.get("user", {}).get("mobile_number"),
    )

    section("9. Roles are enforced on the server")
    status, body = call("GET", "/api/customer/profile/")
    check("customer reads own profile", status == 200, body)
    # A separate browser for the admin, because one cookie jar holds one session.
    admin_browser = Browser()
    admin_browser.call("GET", "/api/auth/csrf/")
    status, admin_login = admin_browser.call(
        "POST", "/api/admin/verify-mfa/", {"code": admin_login_mfa_code(admin_browser)}
    )
    check("second admin session opened", status == 200, admin_login)
    status, body = admin_browser.call("GET", "/api/customer/profile/")
    check("admin blocked from customer API (403)", status == 403, body)
    status, body = call("POST", "/api/admin/change-password/otp/")
    check("customer blocked from admin API (403)", status == 403, body)

    section("10. The session is what authenticates - nothing else")
    # No token, no header: the cookie alone is the credential, repeatedly.
    for attempt in range(3):
        status, body = call("GET", "/api/customer/profile/")
        check(f"cookie alone authenticates (attempt {attempt + 1})", status == 200, body)
    status, _ = _reload(BROWSER).call("GET", "/api/auth/session/")
    check("session survives a reload (fresh jar, same cookie)", status == 200, status)

    section("11. Concurrent sessions are allowed (round 23)")
    second_device = Browser()
    second_device.call("GET", "/api/auth/csrf/")
    clear_otp_state()
    status, body = second_device.call(
        "POST", "/api/customer/send-otp/", {"mobile_number": MOBILE}
    )
    status, body = second_device.call(
        "POST", "/api/customer/verify-otp/",
        {"mobile_number": MOBILE, "code": body.get("dev_otp")},
    )
    check("second login succeeds", status == 200, body)
    check("no duplicate account", body.get("is_new_customer") is False, body.get("is_new_customer"))
    check("second device has its own cookie", second_device.cookie("ums_mart_sessionid") != BROWSER.cookie("ums_mart_sessionid"))
    # Round 23 reversed the old single-session rule: signing in on a second
    # device must NOT sign the first one out.
    status, body = call("GET", "/api/customer/profile/")
    check("first session still works (200)", status == 200, body)
    status, body = second_device.call("GET", "/api/customer/profile/")
    check("second session works (200)", status == 200, body)

    section("12. Equivalent mobile spellings resolve to one account")
    clear_otp_state()
    status, body = call("POST", "/api/customer/send-otp/", {"mobile_number": "+91" + MOBILE})
    check("+91 form accepted", status == 200, body)
    status, body = call(
        "POST",
        "/api/customer/verify-otp/",
        {"mobile_number": "+91" + MOBILE, "code": body.get("dev_otp")},
    )
    check("same account reused", body.get("is_new_customer") is False, body.get("is_new_customer"))

    section("13. Logout ends the session")
    # Logout is CSRF-protected; without the header Django refuses it, and that
    # refusal must not be mistaken for a dead session.
    logout_browser = _reload(BROWSER)
    status, body = logout_browser.call("POST", "/api/customer/logout/")
    check("logout 200", status == 200, body)
    status, body = logout_browser.call("GET", "/api/customer/profile/")
    check("session is gone after logout (401)", status == 401, body)
    # Round 30: the row is deleted, so even a stolen copy of the cookie is dead.
    stolen = Browser()
    stolen.jar.set_cookie(_clone_cookie(BROWSER, "ums_mart_sessionid"))
    status, body = stolen.call("GET", "/api/auth/session/")
    check("old cookie value is useless (401)", status == 401, body)

    section("14. Forgot password never reveals whether an email exists")
    reset_auth_state()
    clear_otp_state()
    status_real, body_real = call("POST", "/api/admin/forgot-password/", {"email": ADMIN_EMAIL})
    status_fake, body_fake = call(
        "POST", "/api/admin/forgot-password/", {"email": "nobody-at-all@example.com"}
    )
    check("same status", status_real == status_fake, (status_real, status_fake))
    check("same message", body_real.get("message") == body_fake.get("message"), body_fake)

    section("15. Password reset ends existing sessions")
    # A dedicated browser, so the reset has a session of its own to kill.
    doomed = Browser()
    doomed.call("GET", "/api/auth/csrf/")
    status, _ = doomed.call(
        "POST", "/api/admin/verify-mfa/", {"code": admin_login_mfa_code(doomed)}
    )
    check("pre-reset session works", doomed.call("GET", "/api/auth/session/")[0] == 200, status)
    doomed_cookie = _clone_cookie(doomed, "ums_mart_sessionid")

    clear_otp_state()
    status, body = call("POST", "/api/admin/forgot-password/", {"email": ADMIN_EMAIL})
    reset_code = body.get("dev_otp")
    status, body = call(
        "POST", "/api/admin/verify-reset-otp/", {"email": ADMIN_EMAIL, "code": reset_code}
    )
    reset_token = body.get("reset_token")
    check("reset token issued", bool(reset_token), body)
    # Reset back to the same password so the account stays usable.
    status, body = call(
        "POST",
        "/api/admin/reset-password/",
        {
            "reset_token": reset_token,
            "new_password": ADMIN_PASSWORD,
            "confirm_password": ADMIN_PASSWORD,
        },
    )
    check("password reset applied", status == 200, body)

    # Round 30: the session rows are deleted, so the cookie is worthless at once -
    # stronger than the old blacklist, which only stopped future token issuance.
    status, body = doomed.call("GET", "/api/auth/session/")
    check("session ended by reset (401)", status == 401, body)

    stolen = Browser()
    stolen.jar.set_cookie(doomed_cookie)
    status, body = stolen.call("GET", "/api/auth/session/")
    check("copied cookie is dead too (401)", status == 401, body)

    print(f"\n=== {_passed} passed, {_failed} failed ===")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
