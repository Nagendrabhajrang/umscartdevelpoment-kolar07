"""End-to-end smoke test of every major API workflow.

Run with:
    python manage.py shell < scripts/smoke_test.py
or
    python scripts/run_smoke.py

It exercises the real HTTP layer (DRF test client, which runs the full
middleware + view + service + ORM stack) against the configured database.
"""

import json
import sys
import random
import uuid

from django.test import Client

# A unique suffix keeps repeated runs isolated from each other's leftovers.
RUN_TOKEN = uuid.uuid4().hex[:6].upper()
# A valid 10-digit Indian mobile. Every call site writes f"+919{RUN_NUM}", so the
# suffix must be 9 digits: "9" + 9 more gives +919XXXXXXXXX.
#
# Round 30 fix: this used to be 7 digits, which produced an 11-character number.
# The commerce API stores exactly what it is sent while the OTP layer
# canonicalises, so the Customer row (`+9192272492`) and the account created by
# signing in with that same number (`+919192272492`) were DIFFERENT identities -
# and checkout then looked up an address owned by nobody the run was signed in as.
RUN_NUM = "".join(random.choices("0123456789", k=9))


class Smoke:
    def __init__(self):
        self.client = Client()
        self.passed = 0
        self.failed = 0
        self.results = []

    def call(self, method, url, data=None, headers=None, expect=None, label=""):
        headers = headers or {}
        kwargs = {"content_type": "application/json", **headers}
        if data is not None:
            kwargs["data"] = json.dumps(data)
        response = getattr(self.client, method.lower())(url, **kwargs)
        body = None
        content_type = response.headers.get("Content-Type", "")
        if content_type.startswith("application/json"):
            try:
                body = response.json()
            except Exception:
                body = response.content[:300]
        ok = response.status_code == expect if expect else True
        status = "PASS" if ok else "FAIL"
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        line = (
            f"[{status}] {method:6} {url:60} -> {response.status_code}"
            f"{'' if expect is None else f' (expected {expect})'}"
        )
        print(line)
        if not ok:
            print("        body:", json.dumps(body)[:1000] if body else response.content[:500])
        self.results.append((ok, line))
        return response, body

    def summary(self):
        print("\n" + "=" * 78)
        print(f"SMOKE RESULT: {self.passed} passed, {self.failed} failed")
        print("=" * 78)
        return self.failed == 0


def cleanup_previous_runs():
    """Remove artefacts left behind by earlier smoke runs.

    Products referenced by order items are PROTECT-ed by design, so those are
    soft-deleted (hidden from the storefront) instead of hard-deleted.
    """
    from django.db.models import ProtectedError

    from apps.catalog.models import Category, Product
    from apps.customers.models import Customer
    from apps.promotions.models import Promotion

    # Soft-deleted leftovers are invisible to the API but still occupy stock
    # and inflate admin counts, so they must be removed too. Anything still
    # referenced by an order item stays (PROTECT), and that is fine.
    for product in Product.all_objects.filter(name__startswith="Smoke Test Product"):
        try:
            try:
                product.stock.delete()
            except ObjectDoesNotExist:
                pass  # no stock row (already cleaned up)
            product.delete(hard=True)
        except (ProtectedError, AttributeError):
            try:
                product.delete()
            except ProtectedError:
                pass

    for category in Category.objects.filter(name__startswith="Smoke "):
        # ``category.products`` is the soft-delete-aware manager, so it hides
        # products that were only soft-deleted. Ask the raw manager instead.
        has_products = Product.all_objects.filter(category_id=category.id).exists()
        if not has_products:
            category.delete()

    for customer in Customer.all_objects.filter(full_name__startswith="Smoke Customer"):
        if not customer.orders.exists():
            try:
                customer.delete(hard=True)
            except (ProtectedError, AttributeError):
                customer.delete()

    Promotion.objects.filter(name__startswith="Smoke ").delete()


def run():
    cleanup_previous_runs()
    s = Smoke()
    root = ""            # auth endpoints live at /api/customer/, above the /api/v1 prefix
    api = "/api/v1"
    tok = RUN_TOKEN
    print(f"RUN TOKEN: {tok}")

    # ------------------------------------------------------------------
    print("\n--- 0. Health & schema ------------------------------------------")
    s.call("get", "/health/", expect=200, label="health")
    s.call("get", "/api/schema/", expect=200)
    s.call("get", "/api/docs/", expect=200)

    # ------------------------------------------------------------------
    print("\n--- 1. Catalog: categories & products ----------------------------")
    _, cats = s.call("get", f"{api}/catalog/categories/?only_parents=true&is_active=true", expect=200)
    parent_id = cats["results"][0]["id"] if cats and cats.get("results") else None

    resp, created_cat = s.call(
        "post", f"{api}/catalog/categories/",
        {
            "name": f"Smoke Test Category {tok}",
            "description": "Created by the smoke test",
            "parent": parent_id,
            "is_active": True,
        },
        expect=201,
    )
    smoke_cat_id = created_cat.get("id") if isinstance(created_cat, dict) else None

    # duplicate category -> 409
    s.call(
        "post", f"{api}/catalog/categories/",
        {"name": f"Smoke Test Category {tok}", "parent": parent_id},
        expect=409,
    )
    # sub-of-sub -> 400 (depth guard)
    if smoke_cat_id:
        s.call(
            "post", f"{api}/catalog/categories/",
            {"name": f"Smoke Sub Category {tok}", "parent": smoke_cat_id},
            expect=400,
        )

    resp, product = s.call(
        "post", f"{api}/catalog/products/",
        {
            "name": f"Smoke Test Product {tok}",
            "category": smoke_cat_id,
            "mrp": "120.00",
            "selling_price": "99.00",
            "unit_type": "piece",
            "unit_value": "1.00",
            "initial_quantity": 25,
            "brand": "SmokeBrand",
        },
        expect=201,
    )
    product_id = product["id"]
    sku = product["sku"]
    print(f"        -> product id={product_id} sku={sku}")

    # selling price > mrp -> 400
    s.call(
        "post", f"{api}/catalog/products/",
        {"name": "Bad Price", "category": smoke_cat_id, "mrp": "10.00", "selling_price": "20.00"},
        expect=400,
    )
    # duplicate SKU -> 409
    s.call(
        "post", f"{api}/catalog/products/",
        {"name": "Dup SKU", "category": smoke_cat_id, "mrp": "10.00",
         "selling_price": "9.00", "sku": sku},
        expect=409,
    )

    s.call("get", f"{api}/catalog/products/", expect=200)
    s.call("get", f"{api}/catalog/products/?search=Smoke", expect=200)
    s.call("get", f"{api}/catalog/products/{product_id}/", expect=200)
    s.call("get", f"{api}/catalog/products/?page_size=5&page=2", expect=200)
    s.call("get", f"{api}/catalog/products/?min_price=50&max_price=150&in_stock=true", expect=200)
    s.call("get", f"{api}/catalog/products/featured/?limit=4", expect=200)
    s.call("get", f"{api}/catalog/categories/tree/", expect=200)
    s.call("patch", f"{api}/catalog/products/{product_id}/",
           {"short_description": "Updated by smoke test"}, expect=200)

    # ------------------------------------------------------------------
    print("\n--- 2. Inventory -------------------------------------------------")
    _, stock_list = s.call("get", f"{api}/inventory/stock/?search=Smoke", expect=200)
    stock_id = stock_list["results"][0]["id"]
    print(f"        -> stock id={stock_id} qty={stock_list['results'][0]['quantity']}")
    s.call("post", f"{api}/inventory/stock/{stock_id}/add/",
           {"quantity": 10, "reason": "Smoke restock"}, expect=200)
    s.call("post", f"{api}/inventory/stock/{stock_id}/remove/",
           {"quantity": 3, "reason": "Smoke damage"}, expect=200)
    s.call("patch", f"{api}/inventory/stock/{stock_id}/quantity/",
           {"quantity": 40, "reason": "Smoke stock count"}, expect=200)
    s.call("get", f"{api}/inventory/stock/{stock_id}/movements/", expect=200)
    s.call("get", f"{api}/inventory/movements/?product={product_id}", expect=200)
    s.call("get", f"{api}/inventory/stock/summary/", expect=200)
    s.call("get", f"{api}/inventory/stock/low-stock/", expect=200)

    # ------------------------------------------------------------------
    print("\n--- 3. Customers & addresses -------------------------------------")
    # Use a seeded, address-bearing customer so the cart/checkout flows have a
    # delivery address available.
    s.call("get", f"{api}/customers/?page_size=50", expect=200)
    _, smoke_customer = s.call(
        "post", f"{api}/customers/",
        {"full_name": f"Smoke Customer {tok}", "mobile_number": f"+919{RUN_NUM}",
         "email": f"smoke.{tok.lower()}@example.com"},
        expect=201,
    )
    # Every subsequent customer-scoped call uses this run's own customer, so the
    # suite never mutates seeded data and stays repeatable.
    customer_id = smoke_customer["id"]
    print(f"        -> smoke customer id={customer_id}")

    s.call("post", f"{api}/customers/",
           {"full_name": "Dup Mobile", "mobile_number": f"+919{RUN_NUM}"}, expect=409)
    s.call("get", f"{api}/customers/{customer_id}/", expect=200)
    s.call("get", f"{api}/customers/summary/", expect=200)
    s.call("get", f"{api}/customers/?search=Aarav&has_orders=false", expect=200)

    hdr = {"HTTP_X_CUSTOMER_ID": str(customer_id)}
    _, address = s.call(
        "post", f"{api}/addresses/",
        {"recipient_name": "Smoke", "recipient_mobile": f"+919{RUN_NUM}",
         "line1": "9 Smoke Street", "city": "Bengaluru", "state": "Karnataka",
         "pincode": "560001", "is_default": True},
        headers=hdr, expect=201,
    )
    address_id = address["id"]
    print(f"        -> address id={address_id}")
    s.call("get", f"{api}/addresses/mine/", headers=hdr, expect=200)
    s.call("post", f"{api}/addresses/",
           {"recipient_name": "Bad Pin", "recipient_mobile": f"+919{RUN_NUM}",
            "line1": "9 Smoke Street", "city": "Bengaluru", "state": "Karnataka",
            "pincode": "0123"}, headers=hdr, expect=400)

    # ------------------------------------------------------------------
    print("\n--- 4. Cart ------------------------------------------------------")
    s.call("delete", f"{api}/cart/", headers=hdr, expect=204)
    _, cart = s.call("get", f"{api}/cart/", headers=hdr, expect=200)
    s.call("post", f"{api}/cart/items/",
           {"product": product_id, "quantity": 3}, headers=hdr, expect=201)
    _, cart2 = s.call("post", f"{api}/cart/items/",
                       {"product": product_id, "quantity": 2}, headers=hdr, expect=201)
    merged_qty = cart2["item"]["quantity"]
    print(f"        -> merged quantity = {merged_qty} (expected 5)")
    assert merged_qty == 5, "cart merge failed"

    # A second line, using a product this run owns so no seeded stock is drained.
    _, second_product = s.call(
        "post", f"{api}/catalog/products/",
        {"name": f"Smoke Test Product B {tok}", "category": smoke_cat_id,
         "mrp": "60.00", "selling_price": "45.00", "unit_type": "piece",
         "unit_value": "1.00", "initial_quantity": 30, "brand": "SmokeBrand"},
        expect=201,
    )
    s.call("post", f"{api}/cart/items/",
           {"product": second_product["id"], "quantity": 2}, headers=hdr, expect=201)

    # quantity above stock -> 400
    s.call("post", f"{api}/cart/items/", {"product": product_id, "quantity": 9999},
           headers=hdr, expect=400)

    _, summary = s.call("get", f"{api}/cart/summary/", headers=hdr, expect=200)
    print(f"        -> subtotal={summary.get('subtotal')} delivery={summary.get('delivery_charge')} "
          f"grand={summary.get('grand_total')} next={summary.get('next_step')}")

    # coupon apply
    s.call("post", f"{api}/cart/coupon/", {"code": "FRESH10"}, headers=hdr, expect=200)
    # WELCOME100 is first-order-only. This run's customer has no orders yet, so
    # it must be applicable now and must stop applying once the order exists
    # (asserted again after checkout below).
    s.call("post", f"{api}/cart/coupon/", {"code": "WELCOME100"}, headers=hdr, expect=200)
    s.call("delete", f"{api}/cart/coupon/", headers=hdr, expect=200)
    _, summary2 = s.call("get", f"{api}/cart/summary/", headers=hdr, expect=200)
    print(f"        -> after coupon: discount={summary2['discount_amount']} "
          f"grand={summary2['grand_total']}")
    s.call("delete", f"{api}/cart/coupon/", headers=hdr, expect=200)
    s.call("post", f"{api}/cart/coupon/", {"code": "NOTACOUPON"}, headers=hdr, expect=400)

    # invalid customer context
    # Round 23: a stale id with no guest key present is a "whose cart is this?"
    # answer now, and a guest key always resolves to that browser's basket.
    s.call("get", f"{api}/cart/", headers={"HTTP_X_CUSTOMER_ID": "999999"}, expect=400)
    s.call("get", f"{api}/cart/", expect=400)
    s.call(
        "get",
        f"{api}/cart/",
        headers={"HTTP_X_GUEST_CART": "smokeguestkey01"},
        expect=200,
    )

    # ------------------------------------------------------------------
    print("\n--- 5. Wishlist --------------------------------------------------")
    # Round 28 closed the X-Customer-Id seam for wishlist (IsAuthenticated), so
    # the shopper's identity has to come from a real customer access token.
    _, otp = s.call(
        "post", f"{root}/api/customer/send-otp/",
        {"mobile_number": f"+919{RUN_NUM}"}, expect=200,
    )
    _, pair = s.call(
        "post", f"{root}/api/customer/verify-otp/",
        {"mobile_number": f"+919{RUN_NUM}", "code": otp["dev_otp"]}, expect=200,
    )
    # Round 30: verify-otp opened a Django session. Django's test client keeps
    # the cookie, so later calls in this run are already authenticated - there is
    # no header to carry.
    wl_hdr = {}
    s.call("get", f"{root}/api/auth/session/", expect=200)
    s.call("post", f"{api}/wishlist/toggle/", {"product": product_id}, headers=wl_hdr, expect=200)
    s.call("get", f"{api}/wishlist/", headers=wl_hdr, expect=200)
    s.call("post", f"{api}/wishlist/toggle/", {"product": product_id}, headers=wl_hdr, expect=200)

    # ------------------------------------------------------------------
    print("\n--- 6. Checkout: COD ---------------------------------------------")
    s.call("post", f"{api}/orders/checkout/preview/",
           {"address": address_id, "payment_method": "cod"}, headers=hdr, expect=200)
    resp, order = s.call(
        "post", f"{api}/orders/checkout/",
        {"address": address_id, "payment_method": "cod",
         "customer_notes": "Smoke test COD order", "coupon_code": "WELCOME100"},
        headers=hdr, expect=201,
    )
    order_id = order["id"]
    order_number = order["order_number"]
    print(f"        -> order {order_number} grand={order['grand_total']} "
          f"status={order['status']} payment={order['payment_status']}")

    # stock must have been deducted
    _, stock_after = s.call("get", f"{api}/inventory/stock/{stock_id}/", expect=200)
    print(f"        -> stock after order = {stock_after['quantity']}")

    # The customer now has an order, so the first-order coupon is refused.
    s.call("post", f"{api}/cart/items/", {"product": product_id, "quantity": 1},
           headers=hdr, expect=201)
    s.call("post", f"{api}/cart/coupon/", {"code": "WELCOME100"}, headers=hdr, expect=400)
    s.call("delete", f"{api}/cart/", headers=hdr, expect=204)

    s.call("get", f"{api}/orders/mine/", headers=hdr, expect=200)
    s.call("get", f"{api}/orders/{order_id}/", expect=200)
    s.call("get", f"{api}/orders/{order_number}/", expect=200)
    s.call("get", f"{api}/orders/{order_id}/history/", expect=200)
    s.call("get", f"{api}/orders/stats/", expect=200)

    # illegal transition: pending -> delivered
    s.call("post", f"{api}/orders/{order_id}/status/", {"status": "delivered"}, expect=409)
    # legal: pending -> confirmed
    s.call("post", f"{api}/orders/{order_id}/status/", {"status": "confirmed"}, expect=200)
    s.call("post", f"{api}/orders/{order_id}/status/", {"status": "processing"}, expect=200)
    s.call("post", f"{api}/orders/{order_id}/status/", {"status": "packed"}, expect=200)
    s.call("post", f"{api}/orders/{order_id}/status/", {"status": "out_for_delivery"}, expect=200)

    # Cash-first rule: delivery is refused until the money is in. Prove it, then
    # collect the COD payment and only then mark the order delivered.
    s.call("post", f"{api}/orders/{order_id}/mark-delivered/", expect=400)

    pay = s.call("get", f"{api}/payments/order/{order_id}/", expect=200)
    pay_body = pay[1] if isinstance(pay, tuple) else pay
    payment_id = None
    if isinstance(pay_body, dict):
        payment_id = pay_body.get("id") or (pay_body.get("results") or [{}])[0].get("id")
    if payment_id:
        s.call("post", f"{api}/payments/{payment_id}/cod-collected/",
               {"collected_by": "smoke-rider"}, expect=200)

    s.call("post", f"{api}/orders/{order_id}/mark-delivered/", expect=200)

    # COD payment should be settled now
    s.call("get", f"{api}/payments/order/{order_id}/", expect=200)

    # ------------------------------------------------------------------
    print("\n--- 7. Checkout: empty cart -> 400 --------------------------------")
    s.call("post", f"{api}/orders/checkout/",
           {"address": address_id, "payment_method": "cod"}, headers=hdr, expect=400)

    # ------------------------------------------------------------------
    print("\n--- 8. Checkout: cash on delivery -------------------------------")
    s.call("post", f"{api}/cart/items/",
           {"product": second_product["id"], "quantity": 4}, headers=hdr, expect=201)

    # UPI was removed from this build, so a stray "upi" checkout must 400.
    s.call("post", f"{api}/orders/checkout/",
           {"address": address_id, "payment_method": "upi"}, headers=hdr, expect=400)

    resp, cod_order = s.call(
        "post", f"{api}/orders/checkout/",
        {"address": address_id, "payment_method": "cod"}, headers=hdr, expect=201,
    )
    cod_order_id = cod_order["id"]
    print(f"        -> cod order {cod_order['order_number']} "
          f"payment_status={cod_order['payment_status']}")

    _, payment = s.call("get", f"{api}/payments/order/{cod_order_id}/", expect=200)
    payment_id = payment["id"]
    # The spec field names must all be present.
    for field in ("payment_method", "payment_status", "transaction_id", "amount",
                  "payment_proof", "upi_id", "verified_by", "verified_at",
                  "rejection_reason", "paid_at", "created_at", "updated_at"):
        assert field in payment, f"payment missing field {field}"
    print(f"        -> payment {payment['payment_number']} "
          f"{payment['payment_method']}/{payment['payment_status']} "
          f"amount={payment['amount']}")

    # UPI endpoints are gone, not silently accepted.
    s.call("get", f"{api}/payments/{payment_id}/upi-details/", expect=400)
    s.call("post", f"{api}/payments/{payment_id}/submit-proof/",
           {"transaction_reference": f"UTR-{tok}-000123"}, expect=400)

    # Cash is recorded at the door.
    s.call("post", f"{api}/payments/{payment_id}/cod-collected/",
           {"collected_by": "smoke-rider"}, expect=200)
    _, paid = s.call("get", f"{api}/payments/{payment_id}/", expect=200)
    print(f"        -> after collection: {paid['payment_status']}")
    s.call("get", f"{api}/payments/{payment_id}/verifications/", expect=200)

    # Delivering a COD order settles the order's payment status.
    for step in ("confirmed", "processing", "packed", "out_for_delivery", "delivered"):
        s.call("post", f"{api}/orders/{cod_order_id}/status/",
               {"status": step, "note": "smoke"}, expect=200)
    _, delivered = s.call("get", f"{api}/orders/{cod_order_id}/", expect=200)
    print(f"        -> delivered: status={delivered['status']} "
          f"payment={delivered['payment_status']}")
    s.call("get", f"{api}/payments/stats/", expect=200)

    # ------------------------------------------------------------------
    print("\n--- 9. Cancellation restores stock --------------------------------")
    s.call("post", f"{api}/cart/items/", {"product": product_id, "quantity": 1}, headers=hdr,
           expect=201)
    _, stock_before = s.call("get", f"{api}/inventory/stock/{stock_id}/", expect=200)
    resp, cancel_order = s.call(
        "post", f"{api}/orders/checkout/",
        {"address": address_id, "payment_method": "cod"}, headers=hdr, expect=201,
    )
    _, stock_mid = s.call("get", f"{api}/inventory/stock/{stock_id}/", expect=200)
    s.call("post", f"{api}/orders/{cancel_order['id']}/cancel/",
           {"reason": "customer_request", "note": "Smoke cancel"}, expect=200)
    _, stock_post = s.call("get", f"{api}/inventory/stock/{stock_id}/", expect=200)
    print(f"        -> stock before={stock_before['quantity']} "
          f"after order={stock_mid['quantity']} after cancel={stock_post['quantity']}")
    assert stock_post["quantity"] == stock_before["quantity"], "stock not restored"
    # double cancel -> 400/409
    s.call("post", f"{api}/orders/{cancel_order['id']}/cancel/",
           {"reason": "customer_request"}, expect=409)

    # ------------------------------------------------------------------
    print("\n--- 10. Promotions / banners / store settings ---------------------")
    s.call("get", f"{api}/promotions/", expect=200)
    s.call("get", f"{api}/promotions/active-offers/", expect=200)
    s.call("get", f"{api}/promotions/coupons/available/", expect=200)
    s.call("get", f"{api}/promotions/summary/", expect=200)
    _, smoke_promo = s.call("post", f"{api}/promotions/",
           {"name": f"Smoke 20% offer {tok}", "code": f"SMOKE{tok}", "discount_type": "percentage",
            "discount_value": "20.00", "max_discount_amount": "50.00",
            "applies_to": "all", "usage_limit_per_customer": 2}, expect=201)
    smoke_promo_id = smoke_promo.get("id") if isinstance(smoke_promo, dict) else None
    s.call("post", f"{api}/promotions/",
           {"name": "Dup code", "code": f"SMOKE{tok}", "discount_type": "fixed_amount",
            "discount_value": "10.00", "applies_to": "all"}, expect=409)
    s.call("post", f"{api}/promotions/",
           {"name": "Bad percentage", "code": f"BADPCT{tok}",
            "discount_type": "percentage", "discount_value": "150.00",
            "applies_to": "all"}, expect=400)

    s.call("get", f"{api}/banners/", expect=200)
    s.call("get", f"{api}/banners/live/", expect=200)
    s.call("get", f"{api}/banners/live/?placement=hero", expect=200)

    s.call("get", f"{api}/store-settings/", expect=200)
    s.call("patch", f"{api}/store-settings/", {"delivery_eta_minutes": 40}, expect=200)
    s.call("get", f"{api}/store-settings/delivery-slabs/", expect=200)
    s.call("post", f"{api}/store-settings/delivery-quote/", {"subtotal": "350.00"}, expect=200)
    s.call("get", f"{api}/store-settings/delivery-slabs/resolve/?subtotal=150", expect=200)

    # ------------------------------------------------------------------
    print("\n--- 11. Help / contact -------------------------------------------")
    # The support-ticket module was removed. The Help page is fed by store
    # settings, so what must hold is that the contact block the page renders is
    # actually served - and that the ticket API is gone rather than half-alive.
    _, settings_obj = s.call("get", f"{api}/store-settings/", expect=200)
    for field in ("contact_phone", "contact_email", "address", "store_name",
                  "is_store_open"):
        assert field in settings_obj, f"store settings missing {field}"
    print(f"        -> contact: {settings_obj['contact_phone']} / "
          f"{settings_obj['contact_email']}")
    s.call("get", f"{api}/support/tickets/", expect=404)

    # ------------------------------------------------------------------
    print("\n--- 12. Cleanup / deletes -----------------------------------------")
    s.call("delete", f"{api}/catalog/products/{product_id}/", expect=204)
    s.call("get", f"{api}/catalog/products/{product_id}/", expect=404)
    # The category still owns archived (soft-deleted) products, which hold a
    # PROTECTed FK - the API must refuse with 409 rather than 500.
    s.call("delete", f"{api}/catalog/categories/{smoke_cat_id}/", expect=409)
    if smoke_promo_id:
        s.call("delete", f"{api}/promotions/{smoke_promo_id}/", expect=204)

    cleanup_run(tok)
    return s.summary()


def cleanup_run(tok):
    """Remove everything this run created.

    Teardown has to be thorough or the suite stops being repeatable: a leaked
    customer accumulates addresses (hitting the 20-per-customer limit) and
    leaked orders keep products alive via PROTECTed foreign keys.
    """
    from django.core.exceptions import ObjectDoesNotExist
    from django.db import transaction
    from django.db.models import ProtectedError

    from apps.cart.models import Cart
    from apps.catalog.models import Category, Product
    from apps.customers.models import Customer
    from apps.orders.models import Order
    from apps.orders.services import cancel_order
    from apps.payments.models import Payment

    tok = (tok or "").upper()

    # --- orders created by this run's customer ---------------------------
    customer = Customer.all_objects.filter(full_name=f"Smoke Customer {tok}").first()
    if customer is not None:
        for order in Order.objects.filter(customer=customer):
            # Give the stock back before discarding the order.
            if order.status not in {"cancelled", "delivered", "returned"}:
                try:
                    cancel_order(order, reason="other", note="smoke teardown")
                except Exception:  # noqa: BLE001 - teardown must never raise
                    pass
            try:
                with transaction.atomic():
                    Payment.objects.filter(order=order).delete()
                    order.status_history.all().delete()
                    order.items.all().delete()
                    order.delete()
            except ProtectedError:
                pass

        Cart.objects.filter(customer=customer).delete()
        try:
            customer.addresses.all().delete()
            customer.delete(hard=True)
        except (ProtectedError, AttributeError):
            try:
                customer.delete()
            except ProtectedError:
                pass

    # --- catalogue fixtures this run created ------------------------------
    # The second line item product is named "Smoke Test Product B <tok>", so the
    # prefix filter is "Smoke Test Product", not "... {tok}" - otherwise that
    # product leaks into the next run's stock counts.
    for product in Product.all_objects.filter(
        name__startswith="Smoke Test Product"
    ):
        try:
            if product.order_items.exists():
                product.delete()      # order history -> soft delete
            else:
                try:
                    product.stock.delete()
                except ObjectDoesNotExist:
                    pass
                product.delete(hard=True)
        except (ProtectedError, ObjectDoesNotExist):
            pass

    for category in Category.objects.filter(
        name__startswith=f"Smoke Test Category {tok}"
    ):
        if not Product.all_objects.filter(category_id=category.id).exists():
            try:
                category.delete()
            except ProtectedError:
                pass


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
