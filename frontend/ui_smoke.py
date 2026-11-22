#!/usr/bin/env python3
"""
Browser smoke test for both React apps.

Drives the real UI in headless Chromium, exercises the flows a user would, and
fails on any console error, page error or failed network request.

    python3 ui_smoke.py            # both apps
    python3 ui_smoke.py customer   # one app
"""
import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("screenshots")
OUT.mkdir(exist_ok=True)

CUSTOMER = "http://127.0.0.1:5173"
ADMIN = "http://127.0.0.1:5174"

# Requests that may legitimately 4xx during a normal session.
IGNORED_STATUS = re.compile(r"(/cart/?$.*(404|400))|(payments/order/\d+/.*404)")

problems = []
shots = []

# Credentials for the automated walk. The suite now has to sign in because the
# apps genuinely gate their private pages - which is the point of the change.
ADMIN_USERNAME = os.environ.get("SMOKE_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("SMOKE_ADMIN_PASSWORD", "UMSMart@Admin2026")
DEMO_MOBILE = os.environ.get("SMOKE_MOBILE", "9876500001")


def clear_otp_state():
    """Drop OTP rows so the 60 s cooldown never stalls a run."""
    import subprocess

    subprocess.run(
        ["psql", "-h", "localhost", "-U", "ums_mart_user", "-d", "ums_mart_db", "-q",
         "-c", "DELETE FROM auth_otp_throttle; DELETE FROM auth_otp_verification;"],
        env={"PGPASSWORD": os.environ.get("DB_PASSWORD", "1234"),
             "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
    )


def grab_dev_code(page, pattern, timeout=15000):
    """Read the 6-digit code the dev-mode banner shows, or None."""
    try:
        page.wait_for_function(
            "() => /dev mode/i.test(document.body.innerText)", timeout=timeout
        )
    except Exception:
        return None
    match = re.search(pattern, page.inner_text("body"))
    return match.group(1) if match else None


def sign_in_customer(page):
    """Fill the basket as a guest.

    Round 25 removed customer authentication from the storefront, so there is no
    sign-in step any more - this just adds two items so the cart and checkout
    screens have something to render.
    """
    visit(page, CUSTOMER + "/products", "products")
    added = 0
    for i in range(2):
        try:
            page.locator("button", has_text=re.compile(r"^Add$")).nth(i).click()
            page.wait_for_timeout(900)
            added += 1
        except Exception:
            problems.append("customer: could not add an item to the cart")
            break
    print(f"  {'guest basket':<28} {added} item(s) added")
    return added > 0


def sign_in_admin(page):
    """Sign the dashboard in with password + emailed code, through the real UI."""
    clear_otp_state()
    visit(page, ADMIN + "/login", "admin login")
    page.fill("#username", ADMIN_USERNAME)
    page.fill("#password", ADMIN_PASSWORD)
    page.get_by_role("button", name="Continue").click()
    code = grab_dev_code(page, r"code\s+(\d{6})")
    if not code:
        problems.append("admin: no dev code appeared on the MFA screen")
        return False
    page.fill("#mfa-code", code)
    page.get_by_role("button", name="Verify and sign in").click()
    page.wait_for_url(lambda u: "/login" not in u, timeout=20000)
    page.wait_for_timeout(800)
    print(f"  {'signed in as admin':<28} {page.url}")
    return True


def attach(page, label):
    """Record console errors, page exceptions and failed requests."""
    def on_console(msg):
        if msg.type == "error":
            text = msg.text
            # React Router future-flag notices and favicon 404s are noise.
            if "favicon" in text or text.startswith("Warning:"):
                return
            problems.append(f"[{label}] console: {text[:220]}")

    def on_pageerror(err):
        problems.append(f"[{label}] pageerror: {str(err)[:220]}")

    def on_response(resp):
        if resp.status >= 400:
            url = resp.url
            if "favicon" in url:
                return
            problems.append(f"[{label}] HTTP {resp.status} {url[:150]}")

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("response", on_response)


def shot(page, name, full=True):
    """Screenshot after forcing every lazy image to load.

    Full-page captures only paint what is inside the viewport, so product
    photos further down the page land in the PNG as empty boxes. Scrolling the
    document, waiting for ``img.complete`` and returning to the top makes the
    capture match what a visitor sees.
    """
    path = OUT / f"{name}.png"
    if full:
        page.evaluate(
            """async () => {
                const step = Math.round(window.innerHeight * 0.8);
                const end = document.body.scrollHeight;
                for (let y = 0; y < end; y += step) {
                    window.scrollTo(0, y);
                    await new Promise(r => setTimeout(r, 90));
                }
                window.scrollTo(0, 0);
                // Only wait on images that have actually STARTED loading.
                // `loading="lazy"` images that never entered the viewport stay
                // complete === false forever and never fire onload, which made
                // this promise hang and stalled the whole smoke run.
                await Promise.race([
                    Promise.all(Array.from(document.images)
                        .filter(img => !img.complete && img.loading !== 'lazy')
                        .map(img => new Promise(r => { img.onload = img.onerror = r; }))),
                    new Promise(r => setTimeout(r, 4000)),
                ]);
                await new Promise(r => setTimeout(r, 450));
            }"""
        )
    page.screenshot(path=str(path), full_page=full)
    shots.append(name)
    print(f"    shot: {name}.png")


def visit(page, url, label, wait=1200):
    page.goto(url, wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(wait)
    print(f"  {label:<28} {page.url}")
    return page


def text_of(page, selector):
    try:
        return page.locator(selector).first.inner_text(timeout=3000).strip()
    except Exception:
        return ""


def run_customer(page):
    print("\n=== CUSTOMER STORE ===")
    attach(page, "customer")

    sign_in_customer(page)

    visit(page, CUSTOMER + "/", "home")
    body = page.inner_text("body")
    assert "UMS" in body, "brand missing"
    # The home page must have rendered real API data.
    cards = page.locator("a[href^='/product/']").count()
    print(f"    product links on home: {cards}")
    if cards < 5:
        problems.append(f"[customer] home shows only {cards} product links (expected >5)")
    shot(page, "01-customer-home")

    # A rail + banner should both exist
    # Element-agnostic: the hero carousel is a div, and pinning the selector to
    # `section` made this locator wait forever once the markup changed.
    if page.locator("[aria-roledescription='carousel']").count() == 0:
        problems.append("[customer] banner carousel missing on home")

    visit(page, CUSTOMER + "/categories", "categories")
    shot(page, "02-customer-categories")

    visit(page, CUSTOMER + "/products", "products")
    n = page.locator("a[href^='/product/']").count()
    print(f"    product grid count: {n}")
    if n < 10:
        problems.append(f"[customer] products page shows only {n} items")
    shot(page, "03-customer-products")

    # Product detail. The id comes from the live catalogue: hard-coding one
    # breaks as soon as the demo data is rebuilt (ids keep climbing).
    first_id = page.evaluate(
        """async () => {
            const r = await fetch('/api/v1/catalog/products/?page_size=1&in_stock=true');
            const d = await r.json();
            return d.results?.[0]?.id ?? null;
        }"""
    )
    if first_id is None:
        problems.append("[customer] no in-stock product to open")
        first_id = 1
    print(f"    opening product #{first_id}")
    visit(page, CUSTOMER + f"/product/{first_id}", "product details")
    title = text_of(page, "h1")
    print(f"    product title: {title!r}")
    if not title:
        problems.append("[customer] product page has no h1")
    shot(page, "04-customer-product-detail")

    # Add to cart from the detail page
    added = False
    for label in ("Add to cart", "Go to cart"):
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_enabled():
                btn.click()
                page.wait_for_timeout(1600)
                added = True
                break
        except Exception:
            continue
    print(f"    add-to-cart clicked: {added}")
    if not added:
        problems.append("[customer] could not click add-to-cart")
    shot(page, "05-customer-added-toast")

    visit(page, CUSTOMER + "/cart", "cart")
    cart_body = page.inner_text("body")
    print(f"    cart text has total: {'To pay' in cart_body or 'Order total' in cart_body}")
    shot(page, "06-customer-cart")

    # Search
    visit(page, CUSTOMER + "/search?q=milk", "search")
    shot(page, "07-customer-search")

    # Checkout (needs the cart populated)
    visit(page, CUSTOMER + "/checkout", "checkout")
    shot(page, "08-customer-checkout")

    for path, label, name in (
        ("/orders", "orders", "09-customer-orders"),
        ("/help", "help", "13-customer-help"),
        ("/orders", "track order", "14-customer-track"),
        ("/does-not-exist", "404 page", "15-customer-404"),
    ):
        visit(page, CUSTOMER + path, label)
        shot(page, name)

    # Mobile viewport check (Android-ish)
    page.set_viewport_size({"width": 390, "height": 844})
    visit(page, CUSTOMER + "/", "home (mobile 390px)")
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    print(f"    horizontal overflow at 390px: {overflow}px")
    if overflow > 2:
        problems.append(f"[customer] horizontal overflow of {overflow}px at 390px width")
    shot(page, "16-customer-home-mobile")

    page.set_viewport_size({"width": 1440, "height": 900})


def run_admin(page):
    print("\n=== ADMIN DASHBOARD ===")
    attach(page, "admin")

    sign_in_admin(page)

    visit(page, ADMIN + "/", "dashboard", wait=2500)
    body = page.inner_text("body")
    shot(page, "20-admin-dashboard")
    zeros = body.count("—")
    print(f"    dashboard rendered, em-dash placeholders: {zeros}")

    for path, label, name in (
        ("/orders", "orders", "21-admin-orders"),
        ("/payments", "payments", "22-admin-payments"),
        ("/products", "products", "23-admin-products"),
        ("/categories", "categories", "24-admin-categories"),
        ("/inventory", "inventory", "25-admin-inventory"),
        ("/customers", "customers", "26-admin-customers"),
        ("/promotions", "promotions", "27-admin-promotions"),
        ("/banners", "banners", "28-admin-banners"),
        ("/settings", "settings", "30-admin-settings"),
    ):
        visit(page, ADMIN + path, label)
        shot(page, name)

    # An admin write path: open the "new product" dialog and check validation.
    visit(page, ADMIN + "/products", "products (form test)")
    try:
        page.get_by_role("button", name="New product").first.click()
        page.wait_for_timeout(900)
        shot(page, "31-admin-product-form")
        page.get_by_role("button", name="Create product").first.click()
        page.wait_for_timeout(1200)
        errs = page.locator("[role='alert']").count()
        print(f"    validation messages shown on empty submit: {errs}")
        if errs == 0:
            problems.append("[admin] empty product form submitted without validation errors")
        shot(page, "32-admin-product-form-errors")
        page.keyboard.press("Escape")
    except Exception as e:
        problems.append(f"[admin] product form interaction failed: {e}")

    # Settings tab switching: every tab must actually swap its panel, and the
    # dialog form's save button must stay on screen while the body scrolls.
    visit(page, ADMIN + "/settings", "settings tabs")
    seen = {}
    for tab in ("Store profile", "Payments", "Delivery", "Delivery slabs", "Holidays"):
        try:
            page.get_by_role("tab", name=tab).first.click()
            page.wait_for_timeout(600)
            panel = page.inner_text("main").strip()
            selected = page.get_by_role("tab", name=tab).first.get_attribute("aria-selected")
            print(f"    tab {tab!r}: {len(panel)} chars, selected={selected}")
            if selected != "true":
                problems.append(f"[admin] settings tab {tab!r} did not become selected")
            seen[tab] = panel
        except Exception as e:
            problems.append(f"[admin] settings tab {tab!r} failed: {e}")
    # Each tab renders different content -> the panels are really switching.
    if len(set(seen.values())) < len(seen):
        problems.append("[admin] two settings tabs rendered identical panels")
    page.get_by_role("tab", name="Delivery slabs").first.click()
    page.wait_for_timeout(700)
    shot(page, "33-admin-settings-delivery")

    # Save button must be reachable without scrolling the dialog by hand.
    visit(page, ADMIN + "/products", "product dialog footer")
    try:
        page.get_by_role("button", name="New product").first.click()
        page.wait_for_timeout(800)
        ok = page.evaluate(
            """() => {
                const d = document.querySelector('[role=dialog]');
                const btn = Array.from(d.querySelectorAll('button'))
                    .find(b => /create product/i.test(b.textContent));
                if (!btn) return null;
                const r = btn.getBoundingClientRect();
                return r.bottom <= window.innerHeight && r.height > 0;
            }"""
        )
        print(f"    dialog save button on screen without scrolling: {ok}")
        if not ok:
            problems.append("[admin] product dialog save button is below the fold")
        page.keyboard.press("Escape")
    except Exception as e:
        problems.append(f"[admin] dialog footer check failed: {e}")

    page.set_viewport_size({"width": 390, "height": 844})
    visit(page, ADMIN + "/", "dashboard (mobile 390px)")
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    print(f"    horizontal overflow at 390px: {overflow}px")
    if overflow > 2:
        problems.append(f"[admin] horizontal overflow of {overflow}px at 390px width")
    shot(page, "34-admin-dashboard-mobile")
    page.set_viewport_size({"width": 1440, "height": 900})


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = ctx.new_page()
        try:
            if which in ("both", "customer"):
                run_customer(page)
            if which in ("both", "admin"):
                run_admin(page)
        finally:
            browser.close()

    print("\n" + "=" * 60)
    print(f"screenshots captured: {len(shots)}")
    if problems:
        print(f"PROBLEMS ({len(problems)}):")
        for prob in problems:
            print("  -", prob)
        sys.exit(1)
    print("NO CONSOLE ERRORS, NO PAGE ERRORS, NO FAILED REQUESTS")


if __name__ == "__main__":
    main()
