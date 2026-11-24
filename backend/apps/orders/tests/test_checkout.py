"""Checkout, order creation, stock movement and status-transition tests."""

from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.cart.services import add_to_cart, get_or_create_active_cart
from apps.orders.models import (
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentMethod,
    PaymentStatus,
    allowed_next_statuses,
)
from apps.orders.services import (
    cancel_order,
    checkout,
    get_order_or_404,
    reorder,
    update_order_status,
)
from apps.inventory.models import StockMovementType
from apps.payments.models import Payment
from apps.payments.services import mark_cod_collected
from apps.promotions.models import AppliesTo, CouponRedemption, DiscountType, Promotion
from common.exceptions import (
    BusinessRuleError,
    ConflictError,
    EmptyResourceError,
    InsufficientStockError,
)
from common.tests.factories import (
    make_address,
    make_customer,
    make_product,
    make_store,
)


class CheckoutServiceTests(TestCase):
    def setUp(self):
        make_store(
            minimum_order_value=Decimal("0.00"),
            delivery_charge=Decimal("40.00"),
            free_delivery_threshold=Decimal("99999.00"),
            default_tax_percent=Decimal("0.00"),
            packaging_charge=Decimal("0.00"),
        )
        self.customer = make_customer()
        self.address = make_address(self.customer)
        self.product = make_product(quantity=50, mrp=Decimal("100.00"),
                                    selling_price=Decimal("80.00"))

    def _fill_cart(self, quantity=2, product=None):
        product = product or self.product
        add_to_cart(self.customer, product, quantity=quantity)
        return get_or_create_active_cart(self.customer)

    def test_checkout_creates_order_with_snapshot(self):
        self._fill_cart(quantity=2)
        order = checkout(
            customer=self.customer, address=self.address,
            payment_method=PaymentMethod.COD,
        )
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.status, OrderStatus.PENDING)
        self.assertEqual(order.payment_method, PaymentMethod.COD)
        self.assertEqual(order.payment_status, PaymentStatus.COD_DUE)
        self.assertEqual(order.subtotal, Decimal("160.00"))
        self.assertEqual(order.delivery_charge, Decimal("40.00"))
        self.assertEqual(order.grand_total, Decimal("200.00"))
        self.assertEqual(order.item_count, 1)
        self.assertEqual(order.total_quantity, 2)

    def test_order_number_is_generated(self):
        self._fill_cart()
        order = checkout(customer=self.customer, address=self.address,
                         payment_method=PaymentMethod.COD)
        self.assertTrue(order.order_number.startswith("UMS-"))

    def test_address_is_snapshotted_not_referenced(self):
        self._fill_cart()
        order = checkout(customer=self.customer, address=self.address,
                         payment_method=PaymentMethod.COD)
        self.address.line1 = "Changed Later"
        self.address.save()
        order.refresh_from_db()
        self.assertEqual(order.delivery_address_line1, "1 Test Street")

    def test_order_items_store_price_snapshot(self):
        self._fill_cart(quantity=3)
        order = checkout(customer=self.customer, address=self.address,
                         payment_method=PaymentMethod.COD)
        item = order.items.first()
        self.assertEqual(item.unit_price, Decimal("80.00"))
        self.assertEqual(item.line_total, Decimal("240.00"))
        self.assertEqual(item.product_name, self.product.name)

        # Changing the product later must not rewrite order history.
        self.product.selling_price = Decimal("5.00")
        self.product.save()
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal("80.00"))

    def test_stock_is_deducted_once(self):
        self._fill_cart(quantity=5)
        before = self.product.stock.quantity
        checkout(customer=self.customer, address=self.address,
                 payment_method=PaymentMethod.COD)
        self.product.stock.refresh_from_db()
        self.assertEqual(self.product.stock.quantity, before - 5)

    def test_stock_movement_is_logged_as_sale(self):
        self._fill_cart(quantity=2)
        order = checkout(customer=self.customer, address=self.address,
                         payment_method=PaymentMethod.COD)
        log = self.product.stock.movements.order_by("-created_at").first()
        self.assertEqual(log.movement_type, StockMovementType.SALE)
        self.assertEqual(log.reference, order.order_number)
        self.assertEqual(log.quantity_change, -2)

    def test_cart_is_converted_and_emptied(self):
        cart = self._fill_cart()
        order = checkout(customer=self.customer, address=self.address,
                         payment_method=PaymentMethod.COD)
        cart.refresh_from_db()
        self.assertEqual(cart.status, "converted")
        self.assertEqual(cart.converted_order_id, order.pk)
        self.assertEqual(cart.items.count(), 0)

    def test_status_history_entry_created(self):
        self._fill_cart()
        order = checkout(customer=self.customer, address=self.address,
                         payment_method=PaymentMethod.COD)
        history = order.status_history.all()
        self.assertEqual(history.count(), 1)
        self.assertEqual(history.first().to_status, OrderStatus.PENDING)

    def test_payment_record_created(self):
        self._fill_cart()
        order = checkout(customer=self.customer, address=self.address,
                         payment_method=PaymentMethod.COD)
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.payment_method, PaymentMethod.COD)
        self.assertEqual(payment.amount, order.grand_total)

    def test_checkout_with_empty_cart_raises(self):
        with self.assertRaises(EmptyResourceError):
            checkout(customer=self.customer, address=self.address,
                     payment_method=PaymentMethod.COD)

    def test_checkout_without_stock_raises_and_creates_nothing(self):
        self._fill_cart(quantity=2)
        # Someone else buys the remaining stock in the meantime.
        Stock = self.product.stock.__class__
        Stock.objects.filter(product_id=self.product.pk).update(quantity=1)
        with self.assertRaises(InsufficientStockError):
            checkout(customer=self.customer, address=self.address,
                     payment_method=PaymentMethod.COD)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_rejects_foreign_address(self):
        self._fill_cart()
        other = make_customer()
        foreign_address = make_address(other)
        with self.assertRaises(BusinessRuleError):
            checkout(customer=self.customer, address=foreign_address,
                     payment_method=PaymentMethod.COD)

    def test_checkout_rejects_below_minimum_order(self):
        make_store(minimum_order_value=Decimal("500.00"))
        self._fill_cart(quantity=1)
        with self.assertRaises(BusinessRuleError) as ctx:
            checkout(customer=self.customer, address=self.address,
                     payment_method=PaymentMethod.COD)
        self.assertEqual(ctx.exception.code, "below_minimum_order_value")

    def test_checkout_respects_store_closed(self):
        make_store(is_store_open=False, maintenance_message="Closed today")
        self._fill_cart()
        with self.assertRaises(BusinessRuleError) as ctx:
            checkout(customer=self.customer, address=self.address,
                     payment_method=PaymentMethod.COD)
        self.assertEqual(ctx.exception.code, "store_closed")

    def test_cod_disabled_is_enforced(self):
        make_store(cod_enabled=False)
        self._fill_cart()
        with self.assertRaises(BusinessRuleError) as ctx:
            checkout(customer=self.customer, address=self.address,
                     payment_method=PaymentMethod.COD)
        self.assertEqual(ctx.exception.code, "cod_disabled")

    def test_invalid_payment_method_is_rejected(self):
        self._fill_cart()
        with self.assertRaises(BusinessRuleError):
            checkout(customer=self.customer, address=self.address,
                     payment_method="bitcoin")

    def test_coupon_is_redeemed_and_usage_incremented(self):
        promotion = Promotion.objects.create(
            name="Flat 20",
            code="FLAT20",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("20.00"),
            applies_to=AppliesTo.ALL,
            usage_limit_per_customer=2,
        )
        self._fill_cart(quantity=2)
        order = checkout(
            customer=self.customer, address=self.address,
            payment_method=PaymentMethod.COD, coupon_code="FLAT20",
        )
        self.assertEqual(order.discount_amount, Decimal("20.00"))
        self.assertEqual(order.coupon_code, "FLAT20")
        promotion.refresh_from_db()
        self.assertEqual(promotion.used_count, 1)
        self.assertTrue(CouponRedemption.objects.filter(order=order).exists())

    def test_coupon_usage_limit_is_enforced(self):
        promotion = Promotion.objects.create(
            name="Once only",
            code="ONCE",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("10.00"),
            applies_to=AppliesTo.ALL,
            usage_limit_per_customer=1,
        )
        self._fill_cart(quantity=1)
        checkout(customer=self.customer, address=self.address,
                 payment_method=PaymentMethod.COD, coupon_code="ONCE")
        # Second order must not get the discount again.
        add_to_cart(self.customer, self.product, quantity=1)
        order2 = checkout(customer=self.customer, address=self.address,
                          payment_method=PaymentMethod.COD, coupon_code="ONCE")
        self.assertEqual(order2.discount_amount, Decimal("0.00"))

    def test_two_checkouts_cannot_reuse_one_cart(self):
        """The cart is locked and converted, so a double submit fails cleanly."""
        self._fill_cart()
        checkout(customer=self.customer, address=self.address,
                 payment_method=PaymentMethod.COD)
        with self.assertRaises(EmptyResourceError):
            checkout(customer=self.customer, address=self.address,
                     payment_method=PaymentMethod.COD)
        self.assertEqual(Order.objects.count(), 1)


class OrderStatusTransitionTests(TestCase):
    def setUp(self):
        make_store(minimum_order_value=Decimal("0.00"))
        self.customer = make_customer()
        self.address = make_address(self.customer)
        self.product = make_product(quantity=20)
        add_to_cart(self.customer, self.product, quantity=2)
        self.order = checkout(
            customer=self.customer, address=self.address,
            payment_method=PaymentMethod.COD,
        )

    def test_allowed_transition_map_is_consistent(self):
        self.assertIn(OrderStatus.PACKED, allowed_next_statuses(OrderStatus.PENDING))
        self.assertIn(OrderStatus.CANCELLED, allowed_next_statuses(OrderStatus.PENDING))
        self.assertEqual(allowed_next_statuses(OrderStatus.CANCELLED), set())
        self.assertEqual(allowed_next_statuses(OrderStatus.REFUNDED), set())

    def test_seven_status_transition_map(self):
        expected = {
            "pending": {"packed", "cancelled"},
            "packed": {"out_for_delivery", "cancelled"},
            "out_for_delivery": {"delivered", "cancelled"},
            "delivered": {"returned"},
            "returned": {"refunded"},
            "cancelled": set(),
            "refunded": set(),
        }
        self.assertEqual(set(OrderStatus.values), set(expected))
        for current, targets in expected.items():
            self.assertEqual(allowed_next_statuses(current), targets)
        for removed in ("confirmed", "processing"):
            with self.assertRaises(BusinessRuleError):
                update_order_status(self.order, removed)

    def test_cancel_out_for_delivery(self):
        update_order_status(self.order, OrderStatus.PACKED)
        update_order_status(self.order, OrderStatus.OUT_FOR_DELIVERY)
        cancel_order(self.order)
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)

    def test_happy_path_transitions(self):
        # Cash-first: the order cannot be delivered until the money is in, so
        # the happy path collects the COD payment at out_for_delivery and only
        # then records the delivery.
        for target in [
            OrderStatus.PACKED,
            OrderStatus.OUT_FOR_DELIVERY,
        ]:
            self.order = update_order_status(self.order, target)
            self.assertEqual(self.order.status, target)

        payment = mark_cod_collected(Payment.objects.get(order=self.order))

        self.order = update_order_status(self.order, OrderStatus.DELIVERED)
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)
        self.assertIsNotNone(self.order.delivered_at)
        self.assertEqual(self.order.payment_status, PaymentStatus.COD_COLLECTED)

    def test_cannot_deliver_before_cash_is_collected(self):
        """The API is the real boundary: hiding the button is not enough."""
        for target in [
            OrderStatus.PACKED,
            OrderStatus.OUT_FOR_DELIVERY,
        ]:
            self.order = update_order_status(self.order, target)

        with self.assertRaises(BusinessRuleError) as ctx:
            update_order_status(self.order, OrderStatus.DELIVERED)
        self.assertEqual(ctx.exception.code, "payment_required_before_delivery")

    def test_illegal_transition_raises_conflict(self):
        with self.assertRaises(ConflictError):
            update_order_status(self.order, OrderStatus.DELIVERED)

    def test_invalid_status_value_raises(self):
        with self.assertRaises(BusinessRuleError):
            update_order_status(self.order, "teleported")

    def test_each_transition_is_logged(self):
        update_order_status(self.order, OrderStatus.PACKED)
        self.assertEqual(self.order.status_history.count(), 2)

    def test_cancel_restores_stock(self):
        # setUp already checked out 2 units, so the on-hand figure is 18.
        self.product.stock.refresh_from_db()
        before = self.product.stock.quantity
        self.assertEqual(before, 18)

        cancel_order(self.order, reason="customer_request", note="Changed mind")
        self.product.stock.refresh_from_db()
        self.assertEqual(self.product.stock.quantity, before + 2)
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)
        self.assertIsNotNone(self.order.cancelled_at)

    def test_cancel_releases_coupon_redemption(self):
        promotion = Promotion.objects.create(
            name="Cancel test", code="CANX",
            discount_type=DiscountType.FIXED, discount_value=Decimal("5.00"),
            applies_to=AppliesTo.ALL,
        )
        add_to_cart(self.customer, self.product, quantity=1)
        order = checkout(customer=self.customer, address=self.address,
                         payment_method=PaymentMethod.COD, coupon_code="CANX")
        promotion.refresh_from_db()
        self.assertEqual(promotion.used_count, 1)

        cancel_order(order)
        promotion.refresh_from_db()
        self.assertEqual(promotion.used_count, 0)

    def test_cannot_cancel_delivered_order(self):
        for target in [
            OrderStatus.PACKED,
            OrderStatus.OUT_FOR_DELIVERY,
        ]:
            self.order = update_order_status(self.order, target)
        mark_cod_collected(Payment.objects.get(order=self.order))
        self.order = update_order_status(self.order, OrderStatus.DELIVERED)

        with self.assertRaises(BusinessRuleError):
            cancel_order(self.order)

    def test_double_cancel_is_refused(self):
        cancel_order(self.order)
        with self.assertRaises(BusinessRuleError):
            cancel_order(self.order)


class ReorderTests(TestCase):
    def setUp(self):
        make_store(minimum_order_value=Decimal("0.00"))
        self.customer = make_customer()
        self.address = make_address(self.customer)
        self.product = make_product(quantity=20)
        add_to_cart(self.customer, self.product, quantity=2)
        self.order = checkout(customer=self.customer, address=self.address,
                             payment_method=PaymentMethod.COD)

    def test_reorder_adds_available_items(self):
        result = reorder(self.customer, self.order)
        self.assertEqual(len(result["added"]), 1)
        self.assertEqual(get_or_create_active_cart(self.customer).items.count(), 1)

    def test_reorder_skips_deleted_products(self):
        self.product.delete()
        result = reorder(self.customer, self.order)
        self.assertEqual(result["added"], [])
        self.assertEqual(len(result["skipped"]), 1)

    def test_reorder_rejects_foreign_order(self):
        other = make_customer()
        with self.assertRaises(BusinessRuleError):
            reorder(other, self.order)


class CheckoutAPITests(APITestCase):
    def setUp(self):
        make_store(minimum_order_value=Decimal("0.00"),
                   delivery_charge=Decimal("0.00"),
                   free_delivery_threshold=Decimal("0.00"))
        self.customer = make_customer()
        self.address = make_address(self.customer)
        self.product = make_product(quantity=30, mrp=Decimal("100"),
                                    selling_price=Decimal("80"))
        self.headers = {"HTTP_X_CUSTOMER_ID": str(self.customer.pk)}

    def _add_item(self, quantity=2):
        return self.client.post(
            "/api/v1/cart/items/", {"product": self.product.pk, "quantity": quantity},
            format="json", **self.headers,
        )

    def test_checkout_returns_201_with_payment(self):
        self._add_item()
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": self.address.pk, "payment_method": "cod"},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("payment", response.data)
        self.assertTrue(response.data["order_number"].startswith("UMS-"))

    def test_upi_checkout_is_rejected(self):
        # UPI was removed: the store is cash on delivery only, so a stray
        # "upi" checkout must fail loudly rather than create an unpayable order.
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": self.address.pk, "payment_method": "upi"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
    def test_checkout_preview_returns_breakdown(self):
        self._add_item()
        response = self.client.post(
            "/api/v1/orders/checkout/preview/",
            {"address": self.address.pk, "payment_method": "cod"},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("grand_total", response.data)
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("160.00"))

    def test_checkout_empty_cart_returns_400(self):
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": self.address.pk, "payment_method": "cod"},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "empty_cart")

    def test_checkout_missing_address_returns_400(self):
        self._add_item()
        response = self.client.post(
            "/api/v1/orders/checkout/", {"payment_method": "cod"},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_unknown_address_returns_404(self):
        self._add_item()
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": 999999, "payment_method": "cod"},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_order_list_and_detail(self):
        self._add_item()
        created = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": self.address.pk, "payment_method": "cod"},
            format="json", **self.headers,
        )
        listed = self.client.get("/api/v1/orders/mine/", **self.headers)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data), 1)

        detail = self.client.get(f"/api/v1/orders/{created.data['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["order_number"], created.data["order_number"])

        by_number = self.client.get(f"/api/v1/orders/{created.data['order_number']}/")
        self.assertEqual(by_number.status_code, status.HTTP_200_OK)

    def test_status_endpoint_enforces_transitions(self):
        self._add_item()
        created = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": self.address.pk, "payment_method": "cod"},
            format="json", **self.headers,
        )
        order_id = created.data["id"]

        bad = self.client.post(f"/api/v1/orders/{order_id}/status/",
                               {"status": "delivered"}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_409_CONFLICT)

        ok = self.client.post(f"/api/v1/orders/{order_id}/status/",
                              {"status": "packed"}, format="json")
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

    def test_cancel_endpoint(self):
        self._add_item()
        created = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": self.address.pk, "payment_method": "cod"},
            format="json", **self.headers,
        )
        response = self.client.post(
            f"/api/v1/orders/{created.data['id']}/cancel/",
            {"reason": "customer_request", "note": "Test"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "cancelled")

    def test_order_creation_via_post_is_not_allowed(self):
        response = self.client.post("/api/v1/orders/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_order_delete_is_not_allowed(self):
        self._add_item()
        created = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": self.address.pk, "payment_method": "cod"},
            format="json", **self.headers,
        )
        response = self.client.delete(f"/api/v1/orders/{created.data['id']}/")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_stats_endpoint(self):
        response = self.client.get("/api/v1/orders/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_orders", response.data)

    def test_history_endpoint(self):
        self._add_item()
        created = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": self.address.pk, "payment_method": "cod"},
            format="json", **self.headers,
        )
        response = self.client.get(f"/api/v1/orders/{created.data['id']}/history/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
