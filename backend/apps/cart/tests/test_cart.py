"""Cart: totals, stock validation, merging, coupons and price snapshots."""

from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cart.models import Cart, CartItem, CartStatus
from apps.cart.services import (
    add_to_cart,
    apply_coupon,
    build_cart_summary,
    clear_cart,
    get_or_create_active_cart,
    merge_carts,
    refresh_cart_prices,
    remove_cart_item,
    update_cart_item,
)
from apps.promotions.models import AppliesTo, DiscountType, Promotion
from common.exceptions import BusinessRuleError, InsufficientStockError
from common.tests.factories import (
    make_customer,
    make_delivery_slab,
    make_product,
    make_store,
)


class CartServiceTests(TestCase):
    def setUp(self):
        make_store()
        self.customer = make_customer()
        self.product = make_product(quantity=20, mrp=Decimal("100.00"),
                                    selling_price=Decimal("80.00"))

    def test_active_cart_is_singleton_per_customer(self):
        first = get_or_create_active_cart(self.customer)
        second = get_or_create_active_cart(self.customer)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Cart.objects.filter(customer=self.customer).count(), 1)

    def test_cart_creation_survives_a_lost_race(self):
        """Two tabs opening at once must both get a cart, not a 500.

        Simulates the losing side of the race: the service's initial lookup
        misses, its INSERT collides with a cart another request committed
        meanwhile, and it must then re-read that cart.

        A SELECT issued while the failed INSERT's transaction is still open
        raises TransactionManagementError - that was the real
        /api/v1/cart/summary/ 500 seen in the browser. Reads that happen after
        that block has rolled back must succeed. Only the service module is
        patched, so the test runner's own queries are untouched.
        """
        from unittest import mock

        from django.db import transaction as db_transaction

        from apps.cart import services as cart_services

        Cart.objects.filter(customer=self.customer).delete()
        competitor = Cart.objects.create(
            customer=self.customer, status=CartStatus.ACTIVE
        )
        real_filter = Cart.objects.filter
        state = {"lookups": 0, "insert_failed": False, "in_block": False}

        class _TrackingAtomic:
            """Mimics transaction.atomic but records whether we are inside it."""

            def __enter__(self):
                state["in_block"] = True
                return None

            def __exit__(self, exc_type, exc, tb):
                state["in_block"] = False
                return False

        class _GuardedManager:
            def __getattr__(self, name):
                return getattr(Cart.objects, name)

            def filter(self, *args, **kwargs):
                state["lookups"] += 1
                if state["lookups"] == 1:
                    return Cart.objects.none()          # initial lookup misses
                if state["insert_failed"] and state["in_block"]:
                    # Exactly what Django raises on an aborted transaction.
                    raise db_transaction.TransactionManagementError(
                        "An error occurred in the current transaction."
                    )
                return real_filter(*args, **kwargs)

            def create(self, *args, **kwargs):
                state["insert_failed"] = True
                raise IntegrityError(
                    'duplicate key value violates unique constraint '
                    '"unique_active_cart_per_customer"'
                )

        with mock.patch.object(cart_services, "Cart") as patched_cart, \
                mock.patch.object(cart_services.transaction, "atomic", _TrackingAtomic):
            patched_cart.objects = _GuardedManager()
            cart = cart_services.get_or_create_active_cart(self.customer)

        self.assertTrue(state["insert_failed"])
        self.assertEqual(state["lookups"], 2)          # miss, then recovery read
        self.assertEqual(cart.pk, competitor.pk)

    def test_add_to_cart_creates_item_with_price_snapshot(self):
        item = add_to_cart(self.customer, self.product, quantity=2)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("80.00"))
        self.assertEqual(item.unit_mrp, Decimal("100.00"))
        self.assertEqual(item.line_total, Decimal("160.00"))

    def test_adding_same_product_merges_quantities(self):
        add_to_cart(self.customer, self.product, quantity=2)
        item = add_to_cart(self.customer, self.product, quantity=3)
        self.assertEqual(item.quantity, 5)
        self.assertEqual(CartItem.objects.count(), 1)

    def test_cannot_add_more_than_available_stock(self):
        with self.assertRaises(BusinessRuleError):
            add_to_cart(self.customer, self.product, quantity=21)

    def test_cannot_add_more_than_max_order_quantity(self):
        product = make_product(quantity=500, max_order_quantity=3)
        with self.assertRaises(BusinessRuleError) as ctx:
            add_to_cart(self.customer, product, quantity=4)
        self.assertEqual(ctx.exception.code, "max_order_quantity_exceeded")

    def test_inactive_product_cannot_be_added(self):
        self.product.status = "inactive"
        self.product.save()
        with self.assertRaises(BusinessRuleError):
            add_to_cart(self.customer, self.product)

    def test_soft_deleted_product_cannot_be_added(self):
        product = make_product(quantity=5)
        product.delete()
        product.refresh_from_db()
        with self.assertRaises(Exception):
            add_to_cart(self.customer, product)

    def test_update_item_quantity_and_removal(self):
        item = add_to_cart(self.customer, self.product, quantity=2)
        updated = update_cart_item(item, 4)
        self.assertEqual(updated.quantity, 4)

        update_cart_item(updated, 0)
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_update_beyond_stock_rejected(self):
        item = add_to_cart(self.customer, self.product, quantity=2)
        with self.assertRaises(InsufficientStockError):
            update_cart_item(item, 999)

    def test_remove_item(self):
        item = add_to_cart(self.customer, self.product, quantity=1)
        remove_cart_item(item)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_clear_cart(self):
        add_to_cart(self.customer, self.product, quantity=1)
        cart = get_or_create_active_cart(self.customer)
        clear_cart(cart)
        self.assertEqual(cart.items.count(), 0)

    def test_totals(self):
        add_to_cart(self.customer, self.product, quantity=2)
        cart = get_or_create_active_cart(self.customer)
        self.assertEqual(cart.subtotal, Decimal("160.00"))
        self.assertEqual(cart.mrp_total, Decimal("200.00"))
        self.assertEqual(cart.savings, Decimal("40.00"))
        self.assertEqual(cart.total_quantity, 2)
        self.assertEqual(cart.item_count, 1)

    def test_refresh_prices_adopts_new_product_price(self):
        item = add_to_cart(self.customer, self.product, quantity=1)
        self.product.selling_price = Decimal("70.00")
        self.product.mrp = Decimal("100.00")
        self.product.save()
        cart = get_or_create_active_cart(self.customer)
        refresh_cart_prices(cart)
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal("70.00"))

    def test_merge_carts(self):
        source = get_or_create_active_cart(self.customer)
        add_to_cart(self.customer, self.product, quantity=1)

        other_customer = make_customer()
        target = get_or_create_active_cart(other_customer)
        other_product = make_product(quantity=5)
        add_to_cart(other_customer, other_product, quantity=2)

        merge_carts(source, target)
        source.refresh_from_db()
        self.assertEqual(source.status, CartStatus.MERGED)
        self.assertEqual(target.items.count(), 2)


class CartPricingTests(TestCase):
    def setUp(self):
        make_store(
            delivery_charge=Decimal("40.00"),
            free_delivery_threshold=Decimal("500.00"),
            minimum_order_value=Decimal("100.00"),
            default_tax_percent=Decimal("0.00"),
            packaging_charge=Decimal("5.00"),
        )
        self.customer = make_customer()

    def test_free_delivery_above_threshold(self):
        product = make_product(quantity=50, mrp=Decimal("600"), selling_price=Decimal("600"))
        add_to_cart(self.customer, product, quantity=1)
        summary = build_cart_summary(get_or_create_active_cart(self.customer))
        self.assertTrue(summary["is_free_delivery"])
        self.assertEqual(Decimal(summary["delivery_charge"]), Decimal("0.00"))
        self.assertEqual(summary["next_step"], "checkout")

    def test_flat_delivery_below_threshold(self):
        product = make_product(quantity=50, mrp=Decimal("200"), selling_price=Decimal("200"))
        add_to_cart(self.customer, product, quantity=1)
        summary = build_cart_summary(get_or_create_active_cart(self.customer))
        self.assertFalse(summary["is_free_delivery"])
        self.assertEqual(Decimal(summary["delivery_charge"]), Decimal("40.00"))
        self.assertEqual(Decimal(summary["amount_to_free_delivery"]), Decimal("300.00"))

    def test_delivery_slab_takes_precedence_over_flat_charge(self):
        make_delivery_slab(
            name="Mid slab",
            min_order_value=Decimal("0.00"),
            max_order_value=Decimal("999.99"),
            delivery_charge=Decimal("15.00"),
        )
        product = make_product(quantity=50, mrp=Decimal("200"), selling_price=Decimal("200"))
        add_to_cart(self.customer, product, quantity=1)
        summary = build_cart_summary(get_or_create_active_cart(self.customer))
        self.assertEqual(Decimal(summary["delivery_charge"]), Decimal("15.00"))

    def test_packaging_and_tax_are_added_to_grand_total(self):
        make_store(
            delivery_charge=Decimal("0.00"),
            free_delivery_threshold=Decimal("0.00"),
            default_tax_percent=Decimal("5.00"),
            packaging_charge=Decimal("10.00"),
        )
        product = make_product(quantity=50, mrp=Decimal("100"), selling_price=Decimal("100"))
        add_to_cart(self.customer, product, quantity=1)
        summary = build_cart_summary(get_or_create_active_cart(self.customer))
        self.assertEqual(Decimal(summary["tax_amount"]), Decimal("5.00"))
        self.assertEqual(Decimal(summary["packaging_charge"]), Decimal("10.00"))
        self.assertEqual(Decimal(summary["grand_total"]), Decimal("115.00"))

    def test_minimum_order_value_creates_issue(self):
        make_store(minimum_order_value=Decimal("500.00"),
                   free_delivery_threshold=Decimal("5000.00"))
        product = make_product(quantity=50, mrp=Decimal("100"), selling_price=Decimal("100"))
        add_to_cart(self.customer, product, quantity=1)
        summary = build_cart_summary(get_or_create_active_cart(self.customer))
        codes = {issue["code"] for issue in summary["issues"]}
        self.assertIn("below_minimum_order_value", codes)
        self.assertEqual(summary["next_step"], "add_items")

    def test_empty_cart_summary(self):
        cart = get_or_create_active_cart(self.customer)
        summary = build_cart_summary(cart)
        self.assertEqual(summary["next_step"], "add_items")
        self.assertIn("empty_cart", {i["code"] for i in summary["issues"]})

    def test_price_change_is_reported_as_issue(self):
        make_store(minimum_order_value=Decimal("0.00"),
                   free_delivery_threshold=Decimal("99999.00"))
        product = make_product(quantity=50, mrp=Decimal("100"), selling_price=Decimal("100"))
        add_to_cart(self.customer, product, quantity=1)
        product.selling_price = Decimal("90")
        product.save()
        summary = build_cart_summary(get_or_create_active_cart(self.customer))
        self.assertIn("price_changed", {i["code"] for i in summary["issues"]})


class CouponTests(TestCase):
    def setUp(self):
        make_store(minimum_order_value=Decimal("0.00"),
                   free_delivery_threshold=Decimal("99999.00"),
                   delivery_charge=Decimal("0.00"))
        self.customer = make_customer()
        self.product = make_product(quantity=50, mrp=Decimal("100"),
                                    selling_price=Decimal("100"))
        add_to_cart(self.customer, self.product, quantity=5)

    def test_percentage_coupon_is_applied(self):
        Promotion.objects.create(
            name="Ten percent",
            code="TEN",
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("10.00"),
            min_order_value=Decimal("0.00"),
            applies_to=AppliesTo.ALL,
        )
        cart = get_or_create_active_cart(self.customer)
        apply_coupon(cart, "TEN")
        summary = build_cart_summary(cart)
        self.assertEqual(Decimal(summary["discount_amount"]), Decimal("50.00"))
        self.assertEqual(Decimal(summary["grand_total"]), Decimal("450.00"))

    def test_percentage_coupon_respects_max_cap(self):
        Promotion.objects.create(
            name="Big percent",
            code="BIG",
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("50.00"),
            max_discount_amount=Decimal("30.00"),
            applies_to=AppliesTo.ALL,
        )
        cart = get_or_create_active_cart(self.customer)
        apply_coupon(cart, "BIG")
        self.assertEqual(
            Decimal(build_cart_summary(cart)["discount_amount"]), Decimal("30.00")
        )

    def test_minimum_order_value_blocks_coupon(self):
        Promotion.objects.create(
            name="High minimum",
            code="HIGH",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("100.00"),
            min_order_value=Decimal("1000.00"),
            applies_to=AppliesTo.ALL,
        )
        cart = get_or_create_active_cart(self.customer)
        with self.assertRaises(BusinessRuleError) as ctx:
            apply_coupon(cart, "HIGH")
        self.assertEqual(ctx.exception.code, "coupon_not_applicable")

    def test_unknown_coupon_is_rejected(self):
        cart = get_or_create_active_cart(self.customer)
        with self.assertRaises(BusinessRuleError):
            apply_coupon(cart, "DOESNOTEXIST")

    def test_expired_coupon_is_rejected(self):
        from datetime import timedelta

        from django.utils import timezone

        Promotion.objects.create(
            name="Expired",
            code="OLD",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("10.00"),
            applies_to=AppliesTo.ALL,
            start_date=timezone.now() - timedelta(days=10),
            end_date=timezone.now() - timedelta(days=1),
        )
        cart = get_or_create_active_cart(self.customer)
        with self.assertRaises(BusinessRuleError):
            apply_coupon(cart, "OLD")

    def test_category_scoped_coupon_only_discounts_matching_items(self):
        from common.tests.factories import make_category

        other_category = make_category(name="Other")
        other_product = make_product(category=other_category, quantity=10,
                                     mrp=Decimal("100"), selling_price=Decimal("100"))
        add_to_cart(self.customer, other_product, quantity=5)

        Promotion.objects.create(
            name="Category offer",
            code="CATONLY",
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("10.00"),
            applies_to=AppliesTo.CATEGORY,
            category=other_category,
        )
        cart = get_or_create_active_cart(self.customer)
        apply_coupon(cart, "CATONLY")
        # 10% of the ₹500 spent in the targeted category only.
        self.assertEqual(
            Decimal(build_cart_summary(cart)["discount_amount"]), Decimal("50.00")
        )

    def test_coupon_invalidated_when_cart_becomes_ineligible(self):
        Promotion.objects.create(
            name="Min 400",
            code="MIN400",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("50.00"),
            min_order_value=Decimal("400.00"),
            applies_to=AppliesTo.ALL,
        )
        cart = get_or_create_active_cart(self.customer)
        apply_coupon(cart, "MIN400")
        cart.refresh_from_db()
        self.assertEqual(cart.coupon_code, "MIN400")

        # Drop the cart below the threshold; the stored coupon must be dropped.
        item = cart.items.first()
        update_cart_item(item, 1)
        cart.refresh_from_db()
        self.assertEqual(cart.coupon_code, "")


class CartAPITests(APITestCase):
    def setUp(self):
        make_store(minimum_order_value=Decimal("0.00"),
                   free_delivery_threshold=Decimal("99999.00"))
        self.customer = make_customer()
        self.product = make_product(quantity=30, mrp=Decimal("100"),
                                    selling_price=Decimal("80"))
        self.headers = {"HTTP_X_CUSTOMER_ID": str(self.customer.pk)}

    def test_customer_context_required(self):
        response = self.client.get("/api/v1/cart/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "customer_context_required")

    def test_unknown_customer_returns_404(self):
        """Round 23: a stale id with a guest key present resolves to the guest
        basket; with no key either, the caller is told to pick a cart."""
        response = self.client.get("/api/v1/cart/", HTTP_X_CUSTOMER_ID="999999")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"]["code"], "customer_context_required"
        )

    def test_guest_cart_is_created_and_owned_by_its_key(self):
        key = "guesttestkey001"
        created = self.client.get("/api/v1/cart/", HTTP_X_GUEST_CART=key)
        self.assertEqual(created.status_code, status.HTTP_200_OK)
        self.assertIsNone(created.data["customer"])

        other = self.client.get("/api/v1/cart/", HTTP_X_GUEST_CART="otherkey00002")
        self.assertEqual(other.data["item_count"], 0)

        added = self.client.post(
            "/api/v1/cart/items/",
            {"product": self.product.pk, "quantity": 2},
            format="json",
            HTTP_X_GUEST_CART=key,
        )
        self.assertEqual(added.status_code, status.HTTP_201_CREATED)
        self.assertEqual(added.data["cart"]["item_count"], 1)

    def test_guest_cart_merges_into_the_account_on_login(self):
        key = "guestmergekey01"
        self.client.post(
            "/api/v1/cart/items/",
            {"product": self.product.pk, "quantity": 3},
            format="json",
            HTTP_X_GUEST_CART=key,
        )
        merged = self.client.post(
            "/api/v1/cart/merge/",
            {},
            format="json",
            HTTP_X_GUEST_CART=key,
            HTTP_X_CUSTOMER_ID=str(self.customer.pk),
        )
        self.assertEqual(merged.status_code, status.HTTP_200_OK)
        self.assertEqual(merged.data["merged_line_count"], 1)
        self.assertEqual(merged.data["item_count"], 1)

        # Idempotent: the guest basket is marked merged, so a retry adds nothing.
        again = self.client.post(
            "/api/v1/cart/merge/",
            {},
            format="json",
            HTTP_X_GUEST_CART=key,
            HTTP_X_CUSTOMER_ID=str(self.customer.pk),
        )
        self.assertEqual(again.data["merged_line_count"], 0)
        self.assertEqual(again.data["item_count"], 1)

    def test_get_creates_active_cart(self):
        response = self.client.get("/api/v1/cart/", **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], CartStatus.ACTIVE)

    def test_add_item_and_duplicate_merges(self):
        first = self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": 2},
            format="json", **self.headers,
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": 3},
            format="json", **self.headers,
        )
        self.assertEqual(second.data["item"]["quantity"], 5)

    def test_add_beyond_stock_returns_409(self):
        """Exceeding stock is a state conflict, not malformed input."""
        response = self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": 999},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "insufficient_stock")

    def test_patch_item_quantity(self):
        created = self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": 2},
            format="json", **self.headers,
        )
        item_id = created.data["item"]["id"]
        patched = self.client.patch(
            f"/api/v1/cart/items/{item_id}/", {"quantity": 6}, format="json", **self.headers
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)

    def test_cannot_modify_another_customers_item(self):
        created = self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": 1},
            format="json", **self.headers,
        )
        item_id = created.data["item"]["id"]
        other = make_customer()
        response = self.client.patch(
            f"/api/v1/cart/items/{item_id}/", {"quantity": 3}, format="json",
            HTTP_X_CUSTOMER_ID=str(other.pk),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_increment_and_decrement(self):
        created = self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": 1},
            format="json", **self.headers,
        )
        item_id = created.data["item"]["id"]
        inc = self.client.post(f"/api/v1/cart/items/{item_id}/increment/", **self.headers)
        self.assertEqual(inc.status_code, status.HTTP_200_OK)
        self.assertEqual(inc.data["items"][0]["quantity"], 2)
        dec = self.client.post(f"/api/v1/cart/items/{item_id}/decrement/", **self.headers)
        self.assertEqual(dec.data["items"][0]["quantity"], 1)
        # Decrement at 1 removes the line entirely.
        self.client.post(f"/api/v1/cart/items/{item_id}/decrement/", **self.headers)
        self.assertEqual(self.client.get("/api/v1/cart/", **self.headers).data["items"], [])

    def test_summary_endpoint(self):
        self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": 2},
            format="json", **self.headers,
        )
        response = self.client.get("/api/v1/cart/summary/", **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("160.00"))

    def test_clear_cart(self):
        self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": 2},
            format="json", **self.headers,
        )
        cleared = self.client.delete("/api/v1/cart/", **self.headers)
        self.assertEqual(cleared.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get("/api/v1/cart/", **self.headers).data["items"], [])

    def test_quantity_validation(self):
        response = self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": 0},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_product_returns_404(self):
        response = self.client.post(
            "/api/v1/cart/items/", {"product": 999999, "quantity": 1},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
