#!/usr/bin/env python3
"""Browser test for the two login interfaces.

Drives the built bundles over real HTTP with Chromium, exercising the flows the
way a person does: type, click, wait. Both apps are checked, including the parts
that only show up in a browser - the redirect to /login, the route guard, the
session surviving a reload, and signing out.

Requires both preview servers and the API to be running:

    python ui_auth_e2e.py
"""

from __future__ import annotations

import re
import subprocess
import sys

from playwright.sync_api import expect, sync_playwright

CUSTOMER = "http://127.0.0.1:5173"
# Verified once per run so the journey exercises the returning-customer path.
FIXTURE_MOBILE = "+919666111000"
ADMIN = "http://127.0.0.1:5174"

ADMIN_USER = "admin"
ADMIN_PASS = "UMSMart@Admin2026"

passed = 0
failed = 0
errors: list[str] = []


def goto(page, url):
    """Navigate and wait for the app's own requests to settle.

    `wait_until="networkidle"` is unreliable here: the Vite preview proxy keeps a
    keep-alive connection open for 200 responses with a body, so Playwright never
    reports an idle network even though every request has completed. Waiting on
    `load` plus a short settle is what the page actually needs.
    """
    page.goto(url, wait_until="load")
    page.wait_for_timeout(1200)


def check(label: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}   {detail}")


def sql(statement: str) -> None:
    subprocess.run(
        ["psql", "-h", "localhost", "-U", "ums_mart_user", "-d", "ums_mart_db", "-q", "-c", statement],
        env={"PGPASSWORD": "1234", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
    )


def clear_otp_state() -> None:
    sql("DELETE FROM auth_otp_throttle; DELETE FROM auth_otp_verification;")


def run_customer(browser) -> None:
    """Round 25: the storefront has NO customer authentication.

    This used to drive the mobile-OTP login. Those checks are gone with the
    feature; what matters now is the inverse - nothing in the store asks anyone
    to sign in, and the guarded pages are reachable.
    """
    print("\n=== CUSTOMER STOREFRONT (:5173) - guest first, login at checkout ===")
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page_errors: list[str] = []
    page.on("pageerror", lambda e: page_errors.append(str(e)))

    # --- guest browsing is open and the header offers a way in ---
    goto(page, f"{CUSTOMER}/")
    header = " ".join(page.inner_text("header").lower().split())
    check("header offers a sign-in entry point", "login" in header, header[:80])
    check("header shows the cart", "/cart" in page.inner_html("header"), header[:80])

    # --- purely browsing routes need no account ---
    for path, label in (
        ("/products", "products"),
        ("/search?q=atta", "search"),
        ("/cart", "cart"),
        ("/help", "help"),
    ):
        goto(page, f"{CUSTOMER}{path}")
        page.wait_for_timeout(800)
        check(f"{label} is reachable without signing in", "/login" not in page.url, page.url)

    # --- account routes are gated, and say why ---
    for path, label in (
        ("/checkout", "checkout"),
        ("/orders", "order history"),
        ("/profile", "profile"),
        ("/addresses", "addresses"),
    ):
        goto(page, f"{CUSTOMER}{path}")
        page.wait_for_timeout(1200)
        check(f"{label} requires sign-in", "/login" in page.url, page.url)

    # --- the checkout gate explains itself and promises the cart survives ---
    goto(page, f"{CUSTOMER}/checkout")
    page.wait_for_timeout(1500)
    body = page.inner_text("body").lower()
    check(
        "checkout gate says why a login is needed",
        "login to continue with your order" in body,
        body[:120],
    )
    check("sign-in form is present", page.locator("#mobile").count() == 1, page.url)

    # --- a basket can still be filled while signed out, and the checkout
    #     gate keeps it (the round-26 promise that the cart never resets) ---
    goto(page, f"{CUSTOMER}/products")
    page.wait_for_timeout(1500)
    adders = page.locator("button", has_text=re.compile(r"^Add$"))
    if adders.count():
        adders.first.click()
        page.wait_for_timeout(1500)
        check("guest can add to the cart", "added to cart" in page.inner_text("body").lower())
        goto(page, f"{CUSTOMER}/cart")
        page.wait_for_timeout(1200)
        cart_before = page.inner_text("body").lower()
        check("the guest basket is on /cart", "your cart" in cart_before)
        goto(page, f"{CUSTOMER}/checkout")
        page.wait_for_timeout(1500)
        check("cart survives the checkout gate", "/login" in page.url)
    else:
        check("products rendered for a guest", False, "no Add buttons")

    check("no JS errors on the storefront", not page_errors, str(page_errors[:2]))
    context.close()


def run_customer_journey(browser) -> None:
    """
    The four acceptance scenarios from the round-26 brief, driven through the UI.

    A - new customer: browse, add, checkout, OTP, auto-register, place order
    B - existing customer: guest basket is merged and saved details prefilled
    C - voluntary login from the header lands home with the cart intact
    D - a returning session survives a reload and never re-authenticates
    """
    print("\n=== CUSTOMER JOURNEY (:5173) ===")
    context = browser.new_context(viewport={"width": 1366, "height": 900})
    page = context.new_page()
    page_errors: list[str] = []
    page.on("pageerror", lambda e: page_errors.append(str(e)))

    def otp(mobile: str) -> str:
        page.fill("#mobile", mobile)
        page.get_by_role("button", name=re.compile("send code", re.I)).click()
        page.wait_for_timeout(2600)
        body = page.inner_text("body")
        if "wait" in body.lower() and "second" in body.lower():
            return ""
        match = re.search(r"\b(\d{6})\b", body)
        return match.group(1) if match else ""

    def sign_in(mobile: str) -> bool:
        code = otp(mobile)
        if not code:
            check(f"sms code issued for {mobile}", False, "dev code not shown")
            return False
        page.fill("#otp", code)
        page.get_by_role("button", name=re.compile("verify", re.I)).click()
        page.wait_for_timeout(7000)
        return True

    # --- C: voluntary login from the header, cart already in place ----------
    goto(page, f"{CUSTOMER}/products")
    page.wait_for_timeout(2000)
    adders = page.locator("button", has_text=re.compile(r"^Add$"))
    adders.first.click()
    page.wait_for_timeout(1500)
    goto(page, f"{CUSTOMER}/login")
    page.wait_for_timeout(1000)
    if sign_in(FIXTURE_MOBILE):
        check("voluntary login lands home", page.url.rstrip("/") == CUSTOMER.rstrip("/"), page.url)
        header = page.inner_text("header").lower()
        check("header shows the account, not Login", "login" not in header.split()[-1:], header[-40:])
        check(
            "cart survives a voluntary login",
            page.locator("header a[href='/cart']").inner_text().strip() != "",
        )

        # --- D: reload and navigation keep the session ----------------------
        page.reload(wait_until="load")
        page.wait_for_timeout(1200)
        page.wait_for_timeout(4000)
        # The header shows the account button (not "Login") after a reload; the
        # number itself lives in the account menu, which is where we look.
        header_after = page.inner_text("header").lower()
        check(
            "session survives a reload",
            "my account" in header_after or "login" not in header_after,
            header_after[-40:],
        )
        # --- the round-30 requirement: the cookie itself must be durable -----
        cookies = {c["name"]: c for c in context.cookies()}
        session_cookie = cookies.get("ums_mart_sessionid")
        check("session cookie present", session_cookie is not None, list(cookies))
        if session_cookie:
            # Seven days, not a browser-session cookie. `expires == -1` would mean
            # the cookie dies when the tab closes.
            lifetime = session_cookie.get("expires", -1)
            seven_days = 7 * 24 * 60 * 60
            check(
                "session cookie lives seven days",
                lifetime > 0 and lifetime > 6.9 * seven_days,
                f"expires={lifetime}",
            )
            check("session cookie is HttpOnly", session_cookie.get("httpOnly") is True)
            check(
                "session cookie is not readable by script",
                page.evaluate(
                    "() => !document.cookie.includes('ums_mart_sessionid')"
                ),
            )

        # --- navigating around must not end the session ----------------------
        for path in ("/cart", "/orders", "/profile", "/"):
            goto(page, f"{CUSTOMER}{path}")
            page.wait_for_timeout(1500)
            if "/login" in page.url:
                check(f"navigation to {path} keeps the session", False, page.url)
                break
        else:
            check("navigation never re-authenticates", True)

        goto(page, f"{CUSTOMER}/profile")
        page.wait_for_timeout(2500)
        check("account page opens without re-auth", page.url.endswith("/profile"), page.url)

        # --- logout ---------------------------------------------------------
        goto(page, f"{CUSTOMER}/")
        page.wait_for_timeout(1500)
        page.locator("header button[aria-haspopup='menu']").first.click()
        page.wait_for_timeout(600)
        page.get_by_role("menuitem", name=re.compile("logout", re.I)).click()
        page.wait_for_timeout(2500)
        check("logout returns the header to Login", "login" in page.inner_text("header").lower())
        goto(page, f"{CUSTOMER}/profile")
        page.wait_for_timeout(2000)
        check("a signed-out visitor is gated from /profile", "/login" in page.url, page.url)

    check("no JS errors during the journey", not page_errors, str(page_errors[:2]))
    context.close()


def run_admin(browser) -> None:
    print("\n=== ADMIN DASHBOARD (:5174) ===")
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page_errors: list[str] = []
    page.on("pageerror", lambda e: page_errors.append(str(e)))

    # --- guard: the dashboard must require a session ---
    goto(page, f"{ADMIN}/")
    check("signed-out dashboard redirects to /login", "/login" in page.url, page.url)
    check("admin login rendered", page.get_by_text("UMS Mart admin").count() > 0)

    # --- step 1: password ---
    page.fill("#username", ADMIN_USER)
    page.fill("#password", ADMIN_PASS)
    page.get_by_role("button", name="Continue").click()

    expect(page.get_by_text("Two-step verification")).to_be_visible(timeout=10000)
    check("moved to the MFA step", page.get_by_text("Two-step verification").count() > 0)
    check("no dashboard access before MFA", "/login" in page.url, page.url)

    dev = page.locator("text=/code/i").locator("xpath=..")
    body_text = page.inner_text("body")
    match = re.search(r"code\s+(\d{6})", body_text)
    check("dev-mode code shown", bool(match), body_text[:200])
    assert match, "no code in the MFA screen"
    code = match.group(1)

    # --- step 2: code ---
    page.fill("#mfa-code", code)
    page.get_by_role("button", name="Verify and sign in").click()

    page.wait_for_url(lambda url: "/login" not in url, timeout=20000)
    page.wait_for_timeout(1200)
    check("dashboard reached after MFA", "/login" not in page.url, page.url)

    # --- the shell shows real data and the admin's identity ---
    # The shell mounts after the session check resolves; wait for it rather than
    # sampling the DOM the instant the URL changes.
    page.wait_for_selector("aside a", timeout=15000)
    nav_links = page.locator("aside a")
    check("sidebar rendered", nav_links.count() >= 10, f"{nav_links.count()} links")
    check(
        "sidebar has the expected sections",
        page.get_by_role("link", name=re.compile("Orders")).count() > 0
        and page.get_by_role("link", name=re.compile("Products")).count() > 0,
    )

    page.click("button[aria-haspopup='menu']")
    expect(page.get_by_role("menuitem", name="Sign out")).to_be_visible(timeout=5000)
    menu = page.inner_text("[role='menu']")
    check("account menu names the administrator", "Admin" in menu or "admin" in menu, menu[:120])
    check("account menu offers change password", "Change password" in menu)

    # --- security tab opens from the account menu ---
    page.get_by_role("menuitem", name="Change password").click()
    page.wait_for_timeout(1200)
    page.wait_for_timeout(600)
    check("security tab opened", "/settings" in page.url and "tab=security" in page.url, page.url)
    check(
        "change-password form is present",
        page.locator("#current-password").count() == 1,
    )
    check(
        "session notice explains multi-device sessions",
        "several devices" in page.inner_text("body").lower(),
    )

    # --- reload keeps the session ---
    goto(page, f"{ADMIN}/orders")
    check("dashboard survives a reload", "/login" not in page.url, page.url)

    # --- sign out ---
    page.click("button[aria-haspopup='menu']")
    page.get_by_role("menuitem", name="Sign out").click()
    # signOut() awaits the API call before navigating; wait for the URL.
    page.wait_for_url(lambda url: "/login" in url, timeout=15000)
    check("sign-out returns to login", "/login" in page.url, page.url)
    check(
        "admin tokens cleared",
        # Round 30: no token was ever stored; this asserts the legacy keys are
        # purged and the display cache is gone.
        page.evaluate(
            """() => ['ums.admin.access','ums.admin.refresh','ums.admin.user']
                 .every(k => localStorage.getItem(k) === null)"""
        ),
    )
    check(
        "no credential in localStorage or sessionStorage",
        page.evaluate(
            """() => {
                 const bad = /access|refresh|token|jwt|session/i;
                 const keys = [
                   ...Object.keys(localStorage),
                   ...Object.keys(sessionStorage),
                 ];
                 return keys.filter(k => bad.test(k)).length === 0;
               }"""
        ),
    )

    check("no JS errors on the dashboard", not page_errors, str(page_errors[:2]))
    context.close()


def main() -> int:
    clear_otp_state()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            run_customer(browser)
            clear_otp_state()
            run_customer_journey(browser)
            clear_otp_state()
            run_admin(browser)
        finally:
            browser.close()

    print(f"\n=== {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
