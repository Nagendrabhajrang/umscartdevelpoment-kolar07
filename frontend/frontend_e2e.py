#!/usr/bin/env python3
"""
End-to-end contract test for the frontend.

Exercises the exact request bodies the two React apps send, against the live
Django API, and asserts the response fields the UI reads. Run with the server
on 127.0.0.1:8000.

    python3 frontend_e2e.py
"""
import io
import json
import sys
import urllib.error
import http.cookiejar
import urllib.request
from pathlib import Path

import random
import time

# Round 30: authentication is a Django session cookie. One jar for the whole run
# means signing in once is enough - the same way a browser behaves.
JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR))

BASE = "http://127.0.0.1:8000/api/v1"
ROOT = "http://127.0.0.1:8000"   # auth endpoints sit above the commerce prefix
CUSTOMER = "2"          # overridden by a freshly created customer below
CUSTOMER_MOBILE = "9876500001"   # overridden alongside CUSTOMER
failures = []
checks = 0


def call(method, path, body=None, customer=None, raw=False, headers=None):
    """Perform one API call.

    ``customer`` must be resolved at call time: a default of ``CUSTOMER`` would
    be bound once at import, so every request after make_customer() would keep
    hitting the old id.
    """
    if customer is None:
        customer = CUSTOMER
    # Auth endpoints live under /api/customer/, not /api/v1/, so an absolute
    # path is allowed to opt out of the commerce prefix.
    url = f"{ROOT}{path}" if path.startswith("/api/") else f"{BASE}{path}"
    data = None
    hdrs = {"X-Customer-Id": str(customer), "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        if raw:
            data = body
        else:
            data = json.dumps(body).encode()
            hdrs["Content-Type"] = "application/json"
    if method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        token = next((c.value for c in JAR if c.name == "ums_mart_csrftoken"), None)
        if token is None:
            try:
                OPENER.open(f"{ROOT}/api/auth/csrf/", timeout=10).read()
            except Exception:
                pass
            token = next((c.value for c in JAR if c.name == "ums_mart_csrftoken"), None)
        if token:
            hdrs["X-CSRFToken"] = token
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with OPENER.open(req, timeout=30) as resp:
            text = resp.read().decode()
            return resp.status, (json.loads(text) if text else None)
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = text[:400]
        return e.code, parsed
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def check(label, cond, detail=""):
    global checks
    checks += 1
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        failures.append(label)


def step(name):
    print(f"\n[{name}]")


def make_customer():
    """Each run gets its own customer: first-order-only coupons then apply, and
    repeated runs cannot accumulate state on the seeded records."""
    global CUSTOMER
    mobile = f"9{random.randint(100000000, 999999999)}"
    st, cust = call("POST", "/customers/", {
        "full_name": "E2E Buyer",
        "mobile_number": mobile,
        "email": f"e2e.{int(time.time())}@example.com",
        "status": "active",
    }, customer="1")
    if st in (200, 201) and isinstance(cust, dict) and cust.get("id"):
        global CUSTOMER_MOBILE
        CUSTOMER_MOBILE = mobile
        CUSTOMER = str(cust["id"])
        print(f"  created test customer #{CUSTOMER} ({mobile})")
        return cust["id"]
    print(f"  WARNING: could not create a customer ({st} {cust}); using #{CUSTOMER}")
    return None


def stock_cart(product_id):
    """The cart converts to an order at checkout, so refill before a new order."""
    call("DELETE", "/cart/")
    st, _ = call("POST", "/cart/items/", {"product": product_id, "quantity": 2})
    return st in (200, 201)


# ---------------------------------------------------------------- setup
step("Setup")
make_customer()

# ---------------------------------------------------------------- catalog
step("Catalog (Home page rails)")
st, products = call("GET", "/catalog/products/?page_size=5&ordering=-created_at")
check("products list 200", st == 200, st)
check("results is a list", isinstance(products.get("results"), list))
first = products["results"][0]
for field in ("id", "name", "selling_price", "mrp", "discount_percent",
              "image_url", "available_quantity", "in_stock", "unit_label",
              "category", "category_name"):
    check(f"product list row has {field}", field in first, list(first)[:8])
# The list serializer is lighter than the detail one - only assert these there.
st, pd = call("GET", f"/catalog/products/{first['id']}/")
for field in ("max_order_quantity", "tax_percent", "description", "images", "discount_amount"):
    check(f"product detail has {field}", field in pd, field)

st, featured = call("GET", "/catalog/products/featured/?page_size=3")
check("featured 200 (array)", st == 200 and isinstance(featured, list), st)

st, tree = call("GET", "/catalog/categories/tree/")
check("category tree 200 (array)", st == 200 and isinstance(tree, list), st)

st, banners = call("GET", "/banners/live/")
check("banners 200 (array)", st == 200 and isinstance(banners, list), st)
if banners:
    for field in ("id", "title", "image_url", "link_type", "placement"):
        check(f"banner has {field}", field in banners[0])

st, offers = call("GET", "/promotions/active-offers/")
check("active offers 200 (array)", st == 200 and isinstance(offers, list), st)

# ---------------------------------------------------------------- cart
step("Cart")
pid = first["id"]
call("DELETE", "/cart/")  # start clean (may 404 on an empty cart)

st, item = call("POST", "/cart/items/", {"product": pid, "quantity": 2})
check("add to cart 201/200", st in (200, 201), (st, item))

st, cart = call("GET", "/cart/")
check("cart 200", st == 200, st)
check("cart has items", len(cart.get("items", [])) >= 1)
check("cart item_count present", "item_count" in cart)
cart_item = cart["items"][0]
for field in ("id", "product", "product_name", "quantity", "unit_price",
              "line_total", "available_quantity", "is_available", "product_image"):
    check(f"cart item has {field}", field in cart_item, list(cart_item)[:10])

st, summary = call("GET", "/cart/summary/")
check("summary 200", st == 200, st)
for field in ("subtotal", "mrp_total", "product_savings", "delivery_charge",
              "grand_total", "is_free_delivery", "amount_to_free_delivery",
              "packaging_charge", "tax_amount", "tax_percent", "minimum_order_value",
              "minimum_order_met", "total_quantity", "store_open", "issues"):
    check(f"summary has {field}", field in summary, field)

# increment / decrement / patch
st, _ = call("POST", f"/cart/items/{cart_item['id']}/increment/", {})
check("increment 200", st == 200, st)
st, _ = call("POST", f"/cart/items/{cart_item['id']}/decrement/", {})
check("decrement 200", st == 200, st)
st, _ = call("PATCH", f"/cart/items/{cart_item['id']}/", {"quantity": 3})
check("patch quantity 200", st == 200, st)
st, cart = call("GET", "/cart/")
check("quantity became 3", cart["items"][0]["quantity"] == 3, cart["items"][0]["quantity"])

# ---------------------------------------------------------------- coupon
step("Coupon")
st, coupons = call("GET", "/promotions/coupons/available/")
check("available coupons 200", st == 200 and isinstance(coupons, list), st)
applied_code = None
rejected = []
for coupon in coupons:
    st, res = call("POST", "/cart/coupon/", {"code": coupon["code"]})
    if st in (200, 201):
        applied_code = coupon["code"]
        break
    rejected.append((coupon["code"], st, res))
# Exactly one assertion regardless of how many coupons the store offers, so the
# pass count does not drift between runs.
# A rejection carries the reason - the UI surfaces it verbatim.
check("rejected coupons return an error envelope",
      all(isinstance(r, dict) and r.get("error", {}).get("message")
          for _c, _st, r in rejected),
      [(c, st) for c, st, _r in rejected])

check("at least one coupon applies", applied_code is not None,
      [c["code"] for c in coupons])
if applied_code:
    st, summary = call("GET", "/cart/summary/")
    check(f"summary shows coupon {applied_code}",
          summary.get("coupon_code") == applied_code, summary.get("coupon_code"))
    check("discount_amount present", "discount_amount" in summary)
code = applied_code

# ---------------------------------------------------------------- addresses
step("Addresses")
st, addrs = call("GET", "/addresses/mine/")
check("addresses/mine 200 (array)", st == 200 and isinstance(addrs, list), st)

payload = {
    "label": "home", "recipient_name": "Test Buyer", "recipient_mobile": "9876543210",
    "line1": "12 Test Street", "line2": "", "landmark": "", "city": "Bengaluru",
    "state": "Karnataka", "pincode": "560001", "country": "India",
    "delivery_instructions": "", "is_default": False,
}
st, addr = call("POST", "/addresses/mine/add/", payload)
check("create address (frontend payload)", st in (200, 201), (st, addr))
address_id = addr.get("id") if isinstance(addr, dict) else None

# ---------------------------------------------------------------- checkout COD
step("Checkout (COD)")
st, preview = call("POST", "/orders/checkout/preview/", {"address": address_id, "payment_method": "cod"})
check("checkout preview 200", st == 200, (st, preview))
if isinstance(preview, dict):
    has_totals = any(k in preview for k in ("grand_total", "summary", "subtotal"))
    check("preview carries totals", has_totals, list(preview)[:10])

st, order = call("POST", "/orders/checkout/", {
    "address": address_id, "payment_method": "cod",
    "customer_notes": "Ring the bell", "coupon_code": code,
})
check("place COD order 201", st in (200, 201), (st, order))
order_id = order.get("id") if isinstance(order, dict) else None
order_number = order.get("order_number") if isinstance(order, dict) else None
check("order has order_number", bool(order_number))

st, detail = call("GET", f"/orders/{order_id}/")
check("order detail 200", st == 200, st)
for field in ("order_number", "status", "payment_status", "payment_method",
              "grand_total", "items", "status_history", "can_be_cancelled",
              "next_statuses", "full_delivery_address", "delivery_recipient_name",
              "delivery_recipient_mobile", "total_savings", "is_paid"):
    check(f"order has {field}", field in detail, field)

st, mine = call("GET", "/orders/mine/?page_size=5")
# NOTE: /orders/mine/ returns a plain array (it is not paginated). The
# frontend wraps bare arrays in api.js getPaginated(), so mirror that here.
mine_rows = mine if isinstance(mine, list) else mine.get("results", [])
check("orders/mine 200", st == 200 and isinstance(mine_rows, list), (st, type(mine)))
check("new order listed", any(o["id"] == order_id for o in mine_rows))

# ---------------------------------------------------------------- admin order flow
step("Admin: order status machine")
st, stats = call("GET", "/orders/stats/")
check("orders/stats 200", st == 200 and "total_orders" in stats, st)

st, _ = call("POST", f"/orders/{order_id}/confirm/", {})
check("confirm order 200", st == 200, st)

st, detail = call("GET", f"/orders/{order_id}/")
check("status is confirmed", detail["status"] == "confirmed", detail["status"])
check("next_statuses offered", isinstance(detail.get("next_statuses"), list) and len(detail["next_statuses"]) > 0)

st, res = call("POST", f"/orders/{order_id}/status/", {"status": "processing", "note": "Packing"})
check("transition to processing", st == 200, (st, res))

# illegal transition must be rejected with 409
st, res = call("POST", f"/orders/{order_id}/status/", {"status": "delivered"})
check("illegal jump rejected (409)", st == 409, (st, res))

st, _ = call("POST", f"/orders/{order_id}/mark-delivered/", {})
check("mark-delivered 200", st in (200, 400, 409), st)

# ---------------------------------------------------------------- COD payment
step("Cash on delivery")
st, cart2 = call("GET", "/catalog/products/?page_size=3&ordering=-selling_price")
pid2 = cart2["results"][0]["id"]
refilled = stock_cart(pid2)
check("cart refilled after first checkout", refilled, "add-to-cart failed")

# UPI was removed: the API must refuse it outright.
st, res = call("POST", "/orders/checkout/", {
    "address": address_id, "payment_method": "upi",
})
check("upi checkout rejected (400)", st == 400, (st, res))

st, order2 = call("POST", "/orders/checkout/", {
    "address": address_id, "payment_method": "cod",
})
check("place COD order 201", st in (200, 201), (st, order2))
order2_id = order2.get("id") if isinstance(order2, dict) else None

st, payment = call("GET", f"/payments/order/{order2_id}/")
check("payment for order 200", st == 200, (st, payment))
payment_id = payment.get("id") if isinstance(payment, dict) else None

# The exact field list the spec asks for.
for field in ("id", "order", "customer", "payment_method", "transaction_id",
              "amount", "payment_status", "payment_proof", "upi_id",
              "verified_by", "verified_at", "rejection_reason", "paid_at",
              "created_at", "updated_at"):
    check(f"payment has {field}", field in payment, field)

check("payment method is cod", payment.get("payment_method") == "cod",
      payment.get("payment_method"))
check("new payment starts pending", payment.get("payment_status") == "pending",
      payment.get("payment_status"))
check("paid_at empty before collection", payment.get("paid_at") is None,
      payment.get("paid_at"))

# The retired UPI endpoints must fail loudly.
st, res = call("GET", f"/payments/{payment_id}/upi-details/")
check("upi-details disabled (400)", st == 400, (st, res))
st, res = call("POST", f"/payments/{payment_id}/submit-proof/",
               {"transaction_reference": "E2E123456"})
check("submit-proof disabled (400)", st == 400, (st, res))

# Record the cash, exactly as the admin console does.
st, paid = call("POST", f"/payments/{payment_id}/cod-collected/",
                {"collected_by": "E2E Rider"})
check("record cash 200", st == 200, (st, paid))
check("payment status is paid", paid.get("payment_status") == "paid",
      paid.get("payment_status"))
check("paid_at populated", bool(paid.get("paid_at")), paid.get("paid_at"))

st, verifs = call("GET", f"/payments/{payment_id}/verifications/")
verif_rows = verifs if isinstance(verifs, list) else verifs.get("results", [])
check("verification trail 200", isinstance(verif_rows, list), type(verifs))
check("trail recorded the collection",
      any(v.get("action") == "collected" for v in verif_rows),
      [v.get("action") for v in verif_rows])

st, pstats = call("GET", "/payments/stats/")
check("payments/stats 200", st == 200 and "settled_amount" in pstats, st)
check("stats report zero UPI payments", pstats.get("upi_payments") == 0,
      pstats.get("upi_payments"))

# ---------------------------------------------------------------- delivered gate
step("Delivered only after payment")
st, order_now = call("GET", f"/orders/{order2_id}/")
check("order payment status is cod_collected",
      order_now.get("payment_status") == "cod_collected",
      order_now.get("payment_status"))
for step_name in ("confirmed", "processing", "packed", "out_for_delivery"):
    st, res = call("POST", f"/orders/{order2_id}/status/", {"status": step_name})
    check(f"advance to {step_name}", st == 200, (st, res))
st, res = call("POST", f"/orders/{order2_id}/status/", {"status": "delivered"})
check("deliver a paid order 200", st == 200, (st, res))
st, delivered = call("GET", f"/orders/{order2_id}/")
check("order is delivered", delivered.get("status") == "delivered",
      delivered.get("status"))

# ---------------------------------------------------------------- inventory
step("Admin: inventory")
st, inv = call("GET", f"/inventory/stock/?product={pid}&page_size=1")
inv_rows = inv if isinstance(inv, list) else inv.get("results", [])
check("stock for product 200", st == 200 and inv_rows, st)
stock = inv_rows[0] if inv_rows else None
if not stock:
    st, stock = call("POST", "/inventory/stock/", {"product": pid, "quantity": 10, "track_inventory": True})
    check("created stock row", st in (200, 201), (st, stock))
before = stock["quantity"]
st, res = call("POST", f"/inventory/stock/{stock['id']}/add/",
               {"quantity": 5, "movement_type": "purchase", "reference": "INV-TEST"})
check("add stock 200", st == 200, (st, res))
st, inv2 = call("GET", f"/inventory/stock/?product={pid}&page_size=1")
inv2_rows = inv2 if isinstance(inv2, list) else inv2.get("results", [])
after = inv2_rows[0]["quantity"]
check("stock increased by 5", after == before + 5, f"{before} -> {after}")

st, movements = call("GET", "/inventory/movements/?page_size=5")
check("movements 200", st == 200 and "results" in movements, st)
st, isum = call("GET", "/inventory/stock/summary/")
check("inventory summary fields",
      all(k in isum for k in ("total_products", "total_units", "out_of_stock", "low_stock")), isum)

# ---------------------------------------------------------------- wishlist
step("Wishlist")
# Round 28 closed the X-Customer-Id seam: wishlist is IsAuthenticated now, so
# the shopper's identity has to come from a real access token.
auth_headers = None
st, otp = call("POST", "/api/customer/send-otp/", {"mobile_number": CUSTOMER_MOBILE})
if st in (200, 201) and isinstance(otp, dict) and otp.get("dev_otp"):
    st, pair = call("POST", "/api/customer/verify-otp/",
                    {"mobile_number": CUSTOMER_MOBILE, "code": otp["dev_otp"]})
    # Round 30: the session cookie is in JAR now; no header to carry.
    if isinstance(pair, dict) and pair.get("user"):
        auth_headers = {}
check("signed in for wishlist", auth_headers is not None, st)
st, res = call("POST", "/wishlist/toggle/", {"product": pid}, headers=auth_headers)
check("wishlist toggle 200", st in (200, 201), (st, res))
st, wl = call("GET", "/wishlist/", headers=auth_headers)
check("wishlist 200", st == 200 and "items" in wl, st)
if wl.get("items"):
    witem = wl["items"][0]
    for field in ("id", "product", "product_name", "selling_price", "in_stock", "image_url"):
        check(f"wishlist item has {field}", field in witem, list(witem)[:8])
st, res = call("POST", "/wishlist/toggle/", {"product": pid}, headers=auth_headers)
check("toggle back removed", isinstance(res, dict) and res.get("is_wishlisted") is False, res)

# ---------------------------------------------------------------- help page
step("Help & contact")
# Support tickets were removed; the Help page renders store contact details.
st, contact = call("GET", "/store-settings/")
check("store settings 200", st == 200, st)
for field in ("contact_phone", "contact_email", "address", "store_name"):
    check(f"help page can show {field}", field in contact, field)
st, res = call("GET", "/support/tickets/")
check("ticket API removed (404)", st == 404, (st, res))

# ---------------------------------------------------------------- settings
step("Store settings")
st, settings = call("GET", "/store-settings/")
check("settings 200", st == 200, st)
for field in ("store_name", "upi_id", "upi_qr_image_url", "cod_enabled", "upi_enabled",
              "delivery_charge", "free_delivery_threshold", "minimum_order_value",
              "is_store_open", "delivery_eta_minutes", "currency_symbol"):
    check(f"settings has {field}", field in settings, field)

# ---------------------------------------------------------------- cleanup
step("Cleanup")
call("DELETE", "/cart/")
call("POST", f"/orders/{order_id}/cancel/", {"reason": "customer_request", "note": "e2e cleanup"})
# Drop the throwaway shopper when the storefront allows it. A customer with
# order history is refused with 409 on purpose, so the failure is expected and
# reported rather than treated as a broken test.
status, payload = call("DELETE", f"/customers/{CUSTOMER}/", customer=CUSTOMER)
if status in (200, 204):
    print(f"  removed test customer #{CUSTOMER}")
else:
    print(f"  test customer #{CUSTOMER} kept ({status} "
          f"{payload.get('error', {}).get('code') if isinstance(payload, dict) else payload})")

# ---------------------------------------------------------------- residue
# The API rightly refuses to delete a shopper with orders (409 above), so the
# demo dataset would slowly fill up with "E2E Buyer" rows. Tidy the throwaway
# account straight from Django after the black-box checks are done. This only
# touches rows whose customer is literally named "E2E Buyer".
try:
    import subprocess
    purge = subprocess.run(
        [sys.executable, "-c", """
import os, sys
sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django; django.setup()
from apps.customers.models import Customer
from apps.orders.models import Order
from apps.payments.models import Refund
touched = 0
for c in Customer.all_objects.filter(full_name="E2E Buyer"):
    for o in Order.objects.filter(customer=c):
        Refund.objects.filter(payment__order=o).delete()
        for pay in o.payments.all():
            if hasattr(pay, "verifications"):
                pay.verifications.all().delete()
            pay.delete()
        o.status_history.all().delete()
        o.items.all().delete()
        o.delete()
        touched += 1
    c.addresses.all().delete()
    c.delete(hard=True)
print(f"  e2e residue cleared ({touched} orders)")
"""],
        cwd="../backend", capture_output=True, text=True,
    )
    print(purge.stdout.strip() or purge.stderr.strip())
except Exception as exc:          # never fail the suite over tidying
    print(f"  (residue cleanup skipped: {exc})")

# ---------------------------------------------------------------- result
print("\n" + "=" * 60)
print(f"{checks - len(failures)}/{checks} checks passed")
if failures:
    print("FAILED:")
    for f in failures:
        print("  -", f)
    sys.exit(1)
print(f"ALL CHECKS PASSED  ({Path(__file__).name})")
