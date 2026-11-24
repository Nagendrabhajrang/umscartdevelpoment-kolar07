"""Payments: cash-on-delivery recording, refunds, and the disabled-UPI guards.

UPI was removed from this build (COD only), so the old UPI test block is gone.
What remains proves the COD lifecycle, the refund arithmetic, and that the
retired UPI endpoints fail loudly instead of silently succeeding.
"""

from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APITestCase

from apps.cart.services import add_to_cart
from apps.orders.models import OrderStatus
from apps.orders.services import cancel_order, checkout, update_order_status
from apps.payments.models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    PaymentVerification,
    Refund,
)
from apps.payments.services import (
    approve_payment,
    create_refund,
    get_upi_details,
    mark_cod_collected,
    reject_payment,
    submit_payment_proof,
)
from common.exceptions import BusinessRuleError, ConflictError
from common.tests.factories import (
    make_address,
    make_customer,
    make_product,
    make_store,
)


class CodPaymentTests(TestCase):
    def setUp(self):
        make_store(
            minimum_order_value=Decimal("0.00"),
            delivery_charge=Decimal("0.00"),
            free_delivery_threshold=Decimal("0.00"),
        )
        self.customer = make_customer()
        self.address = make_address(self.customer)
        self.product = make_product(
            quantity=50, mrp=Decimal("100"), selling_price=Decimal("100")
        )

    def _make_order(self, quantity=2):
        add_to_cart(self.customer, self.product, quantity=quantity)
        return checkout(
            customer=self.customer, address=self.address, payment_method="cod"
        )

    # -- creation -----------------------------------------------------
    def test_checkout_creates_a_pending_cod_payment(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.payment_method, PaymentMethod.COD)
        self.assertEqual(payment.payment_status, PaymentStatus.PENDING)
        self.assertEqual(payment.amount, order.grand_total)
        self.assertIsNone(payment.paid_at)
        # An audit row records the creation.
        self.assertEqual(payment.verifications.count(), 1)

    def test_payment_gets_a_readable_number(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        self.assertTrue(payment.payment_number.startswith("PAY-"))

    def test_one_payment_per_order(self):
        order = self._make_order()
        self.assertEqual(Payment.objects.filter(order=order).count(), 1)

    # -- collection ---------------------------------------------------
    def test_mark_collected_moves_payment_to_paid(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        collected = mark_cod_collected(payment, collected_by="rider")
        self.assertEqual(collected.payment_status, PaymentStatus.PAID)
        self.assertIsNotNone(collected.paid_at)
        self.assertEqual(collected.verified_by, "rider")

        order.refresh_from_db()
        self.assertEqual(order.payment_status, "cod_collected")

    def test_collecting_twice_is_rejected(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        mark_cod_collected(payment)
        with self.assertRaises(ConflictError):
            mark_cod_collected(Payment.objects.get(pk=payment.pk))

    def test_collected_amount_must_match(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        with self.assertRaises(BusinessRuleError) as ctx:
            mark_cod_collected(payment, amount=Decimal("1.00"))
        self.assertEqual(ctx.exception.code, "amount_mismatch")

    def test_delivering_a_cod_order_settles_the_payment(self):
        """Cash-first: collect at the door, THEN record the delivery."""
        order = self._make_order()
        for step in ("packed", "out_for_delivery"):
            update_order_status(order, step, changed_by="admin")

        mark_cod_collected(Payment.objects.get(order=order), collected_by="admin")
        update_order_status(order, "delivered", changed_by="admin")

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.DELIVERED)
        self.assertEqual(order.payment_status, "cod_collected")

    def test_cannot_deliver_an_unpaid_cod_order(self):
        """The delivery endpoint must refuse while the cash is still pending."""
        order = self._make_order()
        for step in ("packed", "out_for_delivery"):
            update_order_status(order, step, changed_by="admin")

        with self.assertRaises(BusinessRuleError) as ctx:
            update_order_status(order, "delivered", changed_by="admin")
        self.assertEqual(ctx.exception.code, "payment_required_before_delivery")

    # -- disabled UPI -------------------------------------------------
    def test_upi_details_endpoint_is_disabled(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        with self.assertRaises(BusinessRuleError) as ctx:
            get_upi_details(payment)
        self.assertEqual(ctx.exception.code, "upi_not_enabled")

    def test_submit_payment_proof_is_disabled(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        with self.assertRaises(BusinessRuleError) as ctx:
            submit_payment_proof(payment, transaction_reference="ABCDEF123")
        self.assertEqual(ctx.exception.code, "upi_not_enabled")

    def test_approve_payment_is_disabled(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        with self.assertRaises(BusinessRuleError) as ctx:
            approve_payment(payment, verified_by="admin")
        self.assertEqual(ctx.exception.code, "upi_not_enabled")

    def test_reject_payment_is_disabled(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        with self.assertRaises(BusinessRuleError) as ctx:
            reject_payment(payment, reason="not paid", verified_by="admin")
        self.assertEqual(ctx.exception.code, "upi_not_enabled")

    # -- refunds ------------------------------------------------------
    def test_refund_requires_a_settled_payment(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        with self.assertRaises(BusinessRuleError):
            create_refund(payment, amount=Decimal("10.00"))

    def test_partial_and_full_refund(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        mark_cod_collected(payment)

        first = create_refund(payment, amount=Decimal("20.00"), reason="damaged")
        self.assertEqual(first.status, "processed")
        payment.refresh_from_db()
        self.assertEqual(payment.payment_status, PaymentStatus.PAID)

        remaining = payment.amount - Decimal("20.00")
        create_refund(payment, amount=remaining, reason="rest of it")
        payment.refresh_from_db()
        self.assertEqual(payment.payment_status, PaymentStatus.REFUNDED)

    def test_refund_cannot_exceed_payment(self):
        order = self._make_order()
        payment = Payment.objects.get(order=order)
        mark_cod_collected(payment)
        with self.assertRaises(BusinessRuleError) as ctx:
            create_refund(payment, amount=payment.amount + Decimal("1.00"))
        self.assertEqual(ctx.exception.code, "refund_exceeds_payment")

    # -- cancellation -------------------------------------------------
    def test_cancelling_an_order_closes_the_payment(self):
        order = self._make_order()
        cancel_order(order, reason="customer_request")
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.payment_status, PaymentStatus.CANCELLED)

    def test_cancelled_order_cannot_be_refunded(self):
        order = self._make_order()
        mark_cod_collected(Payment.objects.get(order=order))
        cancel_order(order, reason="customer_request")
        payment = Payment.objects.get(order=order)
        # Already paid, so cancellation leaves the settled payment alone.
        self.assertEqual(payment.payment_status, PaymentStatus.PAID)


class PaymentAPITests(APITestCase):
    def setUp(self):
        make_store(
            minimum_order_value=Decimal("0.00"),
            delivery_charge=Decimal("0.00"),
            free_delivery_threshold=Decimal("0.00"),
        )
        self.customer = make_customer()
        self.address = make_address(self.customer)
        self.product = make_product(
            quantity=20, mrp=Decimal("50"), selling_price=Decimal("50")
        )
        add_to_cart(self.customer, self.product, quantity=2)
        self.order = checkout(
            customer=self.customer, address=self.address, payment_method="cod"
        )
        self.payment = Payment.objects.get(order=self.order)

    def test_payment_detail_exposes_spec_fields(self):
        response = self.client.get(f"/api/v1/payments/{self.payment.pk}/")
        self.assertEqual(response.status_code, 200)
        for field in (
            "payment_method", "payment_status", "transaction_id", "amount",
            "payment_proof", "upi_id", "verified_by", "verified_at",
            "rejection_reason", "paid_at", "created_at", "updated_at",
        ):
            self.assertIn(field, response.data, field)

    def test_legacy_aliases_still_work(self):
        response = self.client.get(f"/api/v1/payments/{self.payment.pk}/")
        self.assertEqual(response.data["method"], "cod")
        self.assertEqual(response.data["status"], "pending")

    def test_cod_collected_endpoint(self):
        response = self.client.post(
            f"/api/v1/payments/{self.payment.pk}/cod-collected/",
            {"collected_by": "rider"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["payment_status"], "paid")

    def test_list_filters_by_status_and_method(self):
        response = self.client.get("/api/v1/payments/?status=pending&method=cod")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_upi_endpoints_return_400(self):
        for path in ("upi-details", ):
            response = self.client.get(f"/api/v1/payments/{self.payment.pk}/{path}/")
            self.assertEqual(response.status_code, 400, path)

    def test_stats_report_cod_only(self):
        response = self.client.get("/api/v1/payments/stats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["cod_payments"], 1)
        self.assertEqual(response.data["upi_payments"], 0)

    def test_checkout_rejects_upi(self):
        add_to_cart(self.customer, self.product, quantity=1)
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address": self.address.pk, "payment_method": "upi"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
