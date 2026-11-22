"""Inventory: locking, audit trail, stock validation and concurrency."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import InventoryLog, Stock, StockMovementType
from apps.inventory.services import (
    add_stock,
    adjust_stock,
    check_availability,
    reconcile_stock_report,
    remove_stock,
    restore_stock_for_order,
    reserve_stock,
    set_initial_stock,
    set_low_stock_threshold,
)
from common.exceptions import BusinessRuleError, InsufficientStockError
from common.tests.factories import (
    make_address,
    make_customer,
    make_order,
    make_product,
)


class StockModelTests(TestCase):
    def test_stock_created_per_product(self):
        product = make_product(quantity=10)
        self.assertIsNotNone(product.stock)
        self.assertEqual(product.stock.quantity, 10)

    def test_available_quantity_accounts_for_reservations(self):
        product = make_product(quantity=10)
        stock = product.stock
        stock.reserved_quantity = 3
        stock.save()
        self.assertEqual(stock.quantity_available, 7)

    def test_available_is_never_negative(self):
        product = make_product(quantity=2)
        stock = product.stock
        stock.reserved_quantity = 5
        stock.save()
        self.assertEqual(stock.quantity_available, 0)

    def test_negative_quantity_fails_check_constraint(self):
        product = make_product(quantity=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Stock.objects.filter(pk=product.stock.pk).update(quantity=-1)

    def test_low_stock_and_out_of_stock_flags(self):
        product = make_product(quantity=2)
        stock = product.stock
        stock.low_stock_threshold = 5
        stock.save()
        self.assertTrue(stock.is_low_stock)
        self.assertFalse(stock.is_out_of_stock)

    def test_untracked_inventory_always_available(self):
        product = make_product(quantity=0)
        stock = product.stock
        stock.track_inventory = False
        stock.save()
        self.assertFalse(stock.is_out_of_stock)
        self.assertTrue(check_availability(product, 1_000))


class StockServiceTests(TestCase):
    def test_add_stock_increments_and_logs(self):
        product = make_product(quantity=5)
        stock = add_stock(product, 10, reference="PO-1", reason="Goods received")
        self.assertEqual(stock.quantity, 15)
        log = InventoryLog.objects.filter(product=product).order_by("-created_at").first()
        self.assertEqual(log.movement_type, StockMovementType.PURCHASE)
        self.assertEqual(log.quantity_change, 10)
        self.assertEqual(log.quantity_before, 5)
        self.assertEqual(log.quantity_after, 15)

    def test_add_stock_rejects_zero_and_negative(self):
        product = make_product(quantity=5)
        with self.assertRaises(BusinessRuleError):
            add_stock(product, 0)
        with self.assertRaises(BusinessRuleError):
            add_stock(product, -3)

    def test_remove_stock_decrements_and_logs(self):
        product = make_product(quantity=10)
        stock = remove_stock(product, 4, reason="Damaged in transit")
        self.assertEqual(stock.quantity, 6)
        log = InventoryLog.objects.filter(product=product).order_by("-created_at").first()
        self.assertEqual(log.quantity_change, -4)

    def test_remove_more_than_available_raises(self):
        product = make_product(quantity=3)
        with self.assertRaises(InsufficientStockError):
            remove_stock(product, 5)
        product.stock.refresh_from_db()
        self.assertEqual(product.stock.quantity, 3)

    def test_adjust_stock_sets_absolute_value(self):
        product = make_product(quantity=20)
        stock = adjust_stock(product, 7, reason="Stock count")
        self.assertEqual(stock.quantity, 7)

    def test_adjust_to_same_value_makes_no_log(self):
        product = make_product(quantity=5)
        before = InventoryLog.objects.filter(product=product).count()
        adjust_stock(product, 5)
        self.assertEqual(InventoryLog.objects.filter(product=product).count(), before)

    def test_adjust_stock_rejects_negative(self):
        product = make_product(quantity=5)
        with self.assertRaises(BusinessRuleError):
            adjust_stock(product, -1)

    def test_reserve_stock_cannot_exceed_available(self):
        product = make_product(quantity=3)
        with self.assertRaises(InsufficientStockError):
            reserve_stock(product, 4)
        stock = reserve_stock(product, 2)
        self.assertEqual(stock.reserved_quantity, 2)
        self.assertEqual(stock.quantity_available, 1)

    def test_set_initial_stock_is_idempotent(self):
        product = make_product(quantity=10)
        set_initial_stock(product, quantity=0)
        product.stock.refresh_from_db()
        self.assertEqual(product.stock.quantity, 10)

    def test_threshold_update(self):
        product = make_product(quantity=10)
        stock = set_low_stock_threshold(product, 15)
        self.assertEqual(stock.low_stock_threshold, 15)
        self.assertTrue(stock.is_low_stock)

    def test_order_deduction_and_restoration_round_trip(self):
        from apps.inventory.services import deduct_stock_for_order

        customer = make_customer()
        product = make_product(quantity=10)
        order = make_order(
            customer,
            address=make_address(customer),
            items=[{"product": product, "quantity": 3,
                    "unit_price": Decimal("80.00")}],
        )
        deduct_stock_for_order(order)
        product.stock.refresh_from_db()
        self.assertEqual(product.stock.quantity, 7)

        restore_stock_for_order(order)
        product.stock.refresh_from_db()
        self.assertEqual(product.stock.quantity, 10)

    def test_deduction_rolls_back_entirely_when_one_item_is_short(self):
        from apps.inventory.services import deduct_stock_for_order

        customer = make_customer()
        ok_product = make_product(quantity=10)
        short_product = make_product(quantity=1)
        order = make_order(
            customer,
            address=make_address(customer),
            items=[
                {"product": ok_product, "quantity": 2, "unit_price": Decimal("80.00")},
                {"product": short_product, "quantity": 5, "unit_price": Decimal("80.00")},
            ],
        )
        with self.assertRaises(InsufficientStockError):
            with transaction.atomic():
                deduct_stock_for_order(order)

        ok_product.stock.refresh_from_db()
        short_product.stock.refresh_from_db()
        # Neither product may be touched when the batch fails.
        self.assertEqual(ok_product.stock.quantity, 10)
        self.assertEqual(short_product.stock.quantity, 1)

    def test_reconcile_report_flags_inconsistency(self):
        product = make_product(quantity=10)
        Stock.objects.filter(pk=product.stock.pk).update(quantity=99)
        discrepancies = reconcile_stock_report()
        self.assertTrue(any(d["product_id"] == product.pk for d in discrepancies))


class StockAPITests(APITestCase):
    def test_list_and_detail(self):
        product = make_product(quantity=8)
        listed = self.client.get("/api/v1/inventory/stock/")
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        detail = self.client.get(f"/api/v1/inventory/stock/{product.stock.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["quantity_available"], 8)

    def test_add_and_remove_actions(self):
        product = make_product(quantity=5)
        added = self.client.post(
            f"/api/v1/inventory/stock/{product.stock.pk}/add/",
            {"quantity": 5, "reason": "Restock"},
            format="json",
        )
        self.assertEqual(added.status_code, status.HTTP_200_OK)
        self.assertEqual(added.data["quantity"], 10)

        removed = self.client.post(
            f"/api/v1/inventory/stock/{product.stock.pk}/remove/",
            {"quantity": 2, "reason": "Damage"},
            format="json",
        )
        self.assertEqual(removed.status_code, status.HTTP_200_OK)
        self.assertEqual(removed.data["quantity"], 8)

    def test_remove_beyond_stock_returns_409(self):
        product = make_product(quantity=1)
        response = self.client.post(
            f"/api/v1/inventory/stock/{product.stock.pk}/remove/",
            {"quantity": 10},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "insufficient_stock")

    def test_set_quantity_action(self):
        from apps.inventory.views import StockViewSet  # noqa: F401

        product = make_product(quantity=5)
        response = self.client.patch(
            f"/api/v1/inventory/stock/{product.stock.pk}/quantity/",
            {"quantity": 42, "reason": "Count"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["quantity"], 42)

    def test_negative_quantity_returns_400(self):
        product = make_product(quantity=5)
        response = self.client.patch(
            f"/api/v1/inventory/stock/{product.stock.pk}/quantity/",
            {"quantity": -5},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_movements_endpoint(self):
        product = make_product(quantity=5)
        add_stock(product, 3, reference="PO-9")
        response = self.client.get(
            f"/api/v1/inventory/stock/{product.stock.pk}/movements/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_low_stock_and_summary_endpoints(self):
        product = make_product(quantity=1)
        set_low_stock_threshold(product, 5)
        low = self.client.get("/api/v1/inventory/stock/low-stock/")
        self.assertEqual(low.status_code, status.HTTP_200_OK)
        summary = self.client.get("/api/v1/inventory/stock/summary/")
        self.assertIn("total_products", summary.data)

    def test_create_stock_row_not_allowed(self):
        response = self.client.post("/api/v1/inventory/stock/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_movement_log_is_read_only(self):
        product = make_product(quantity=2)
        log = InventoryLog.objects.filter(product=product).first()
        deleted = self.client.delete(f"/api/v1/inventory/movements/{log.pk}/")
        self.assertEqual(deleted.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
