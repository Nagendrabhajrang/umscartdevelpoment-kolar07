"""Store settings: singleton behaviour, delivery charges and holidays."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.store_settings.models import DeliverySlab, StoreHoliday, StoreSettings
from apps.store_settings.services import (
    assert_store_open,
    calculate_delivery_charge,
    create_delivery_slab,
    create_holiday,
)
from common.exceptions import BusinessRuleError
from common.tests.factories import make_delivery_slab, make_store


class StoreSettingsModelTests(TestCase):
    def test_singleton_is_always_pk_1(self):
        first = StoreSettings.load()
        second = StoreSettings(store_name="Other")
        second.save()
        self.assertEqual(second.pk, 1)
        self.assertEqual(StoreSettings.objects.count(), 1)

    def test_load_creates_defaults(self):
        settings_obj = StoreSettings.load()
        self.assertEqual(settings_obj.store_name, "UMS Mart")
        self.assertEqual(settings_obj.currency_code, "INR")

    def test_defaults_are_sane(self):
        settings_obj = make_store()
        self.assertTrue(settings_obj.is_store_open)
        self.assertTrue(settings_obj.cod_enabled)
        self.assertTrue(settings_obj.upi_enabled)

    def test_slab_applies_to_range(self):
        slab = make_delivery_slab(min_order_value=Decimal("200"),
                                  max_order_value=Decimal("499"),
                                  delivery_charge=Decimal("25"))
        self.assertFalse(slab.applies_to(Decimal("199")))
        self.assertTrue(slab.applies_to(Decimal("200")))
        self.assertTrue(slab.applies_to(Decimal("499")))
        self.assertFalse(slab.applies_to(Decimal("500")))

    def test_open_ended_slab(self):
        slab = make_delivery_slab(min_order_value=Decimal("500"), max_order_value=None,
                                  delivery_charge=Decimal("0"))
        self.assertTrue(slab.applies_to(Decimal("5000")))
        self.assertTrue(slab.is_free)

    def test_holiday_unique_date(self):
        from django.core.exceptions import ValidationError

        today = timezone.localdate()
        create_holiday(date=today, reason="Festival")
        with self.assertRaises(ValidationError):
            create_holiday(date=today, reason="Duplicate")

    def test_holiday_date_unique_constraint_exists_in_db(self):
        field = StoreHoliday._meta.get_field("date")
        self.assertTrue(field.unique)


class DeliveryChargeTests(TestCase):
    def test_free_above_threshold(self):
        make_store(delivery_charge=Decimal("40"),
                   free_delivery_threshold=Decimal("500"))
        quote = calculate_delivery_charge(Decimal("500"))
        self.assertTrue(quote["is_free_delivery"])
        self.assertEqual(quote["delivery_charge"], Decimal("0.00"))

    def test_flat_charge_below_threshold(self):
        make_store(delivery_charge=Decimal("40"),
                   free_delivery_threshold=Decimal("500"))
        quote = calculate_delivery_charge(Decimal("200"))
        self.assertFalse(quote["is_free_delivery"])
        self.assertEqual(quote["delivery_charge"], Decimal("40.00"))
        self.assertEqual(quote["amount_to_free_delivery"], Decimal("300.00"))

    def test_slab_overrides_flat_charge(self):
        make_store(delivery_charge=Decimal("40"),
                   free_delivery_threshold=Decimal("500"))
        make_delivery_slab(name="Small", min_order_value=Decimal("0"),
                           max_order_value=Decimal("299"),
                           delivery_charge=Decimal("20"))
        quote = calculate_delivery_charge(Decimal("150"))
        self.assertEqual(quote["delivery_charge"], Decimal("20.00"))
        self.assertEqual(quote["applied_slab"], "Small")

    def test_highest_matching_slab_wins(self):
        make_store(delivery_charge=Decimal("40"),
                   free_delivery_threshold=Decimal("5000"))
        make_delivery_slab(name="Low", min_order_value=Decimal("0"),
                           max_order_value=Decimal("1000"),
                           delivery_charge=Decimal("30"))
        make_delivery_slab(name="High", min_order_value=Decimal("300"),
                           max_order_value=Decimal("1000"),
                           delivery_charge=Decimal("10"))
        quote = calculate_delivery_charge(Decimal("400"))
        self.assertEqual(quote["applied_slab"], "High")
        self.assertEqual(quote["delivery_charge"], Decimal("10.00"))

    def test_inactive_slab_is_ignored(self):
        make_store(delivery_charge=Decimal("40"),
                   free_delivery_threshold=Decimal("5000"))
        make_delivery_slab(name="Off", delivery_charge=Decimal("0"), is_active=False)
        quote = calculate_delivery_charge(Decimal("100"))
        self.assertEqual(quote["delivery_charge"], Decimal("40.00"))

    def test_zero_charge_slab_is_free(self):
        make_store(delivery_charge=Decimal("40"),
                   free_delivery_threshold=Decimal("5000"))
        make_delivery_slab(name="Free", min_order_value=Decimal("0"),
                           max_order_value=None, delivery_charge=Decimal("0"))
        quote = calculate_delivery_charge(Decimal("100"))
        self.assertTrue(quote["is_free_delivery"])


class StoreOpenTests(TestCase):
    def test_open_store_passes(self):
        make_store(is_store_open=True)
        assert_store_open()  # must not raise

    def test_closed_store_raises_with_message(self):
        make_store(is_store_open=False, maintenance_message="Back at 6pm")
        with self.assertRaises(BusinessRuleError) as ctx:
            assert_store_open()
        self.assertEqual(ctx.exception.code, "store_closed")
        self.assertIn("Back at 6pm", str(ctx.exception.detail))

    def test_holiday_blocks_orders(self):
        make_store(is_store_open=True)
        StoreHoliday.objects.create(date=timezone.localdate(), reason="Diwali")
        with self.assertRaises(BusinessRuleError) as ctx:
            assert_store_open()
        self.assertEqual(ctx.exception.code, "store_holiday")

    def test_future_holiday_does_not_block(self):
        make_store(is_store_open=True)
        StoreHoliday.objects.create(
            date=timezone.localdate() + timedelta(days=3), reason="Upcoming"
        )
        assert_store_open()


class StoreSettingsAPITests(APITestCase):
    def test_get_settings(self):
        make_store()
        response = self.client.get("/api/v1/store-settings/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["store_name"], "UMS Mart")

    def test_patch_settings(self):
        make_store()
        response = self.client.patch(
            "/api/v1/store-settings/", {"delivery_eta_minutes": 30}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["delivery_eta_minutes"], 30)
        self.assertEqual(response.data["delivery_eta_minutes"], 30)

    def test_cannot_disable_both_payment_methods(self):
        make_store(cod_enabled=True, upi_enabled=True)
        response = self.client.patch(
            "/api/v1/store-settings/",
            {"cod_enabled": False, "upi_enabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_free_delivery_threshold_below_minimum_returns_400(self):
        make_store(minimum_order_value=Decimal("500"),
                   free_delivery_threshold=Decimal("1000"))
        response = self.client.patch(
            "/api/v1/store-settings/",
            {"free_delivery_threshold": "100.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delivery_quote_endpoint(self):
        make_store(delivery_charge=Decimal("40"),
                   free_delivery_threshold=Decimal("500"))
        response = self.client.post(
            "/api/v1/store-settings/delivery-quote/", {"subtotal": "300.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["delivery_charge"]), Decimal("40.00"))

    def test_delivery_quote_free(self):
        make_store(delivery_charge=Decimal("40"),
                   free_delivery_threshold=Decimal("500"))
        response = self.client.post(
            "/api/v1/store-settings/delivery-quote/", {"subtotal": "750.00"},
            format="json",
        )
        self.assertTrue(response.data["is_free_delivery"])

    def test_delivery_slab_crud(self):
        list_url = "/api/v1/store-settings/delivery-slabs/"
        created = self.client.post(
            list_url,
            {"name": "New slab", "min_order_value": "0.00",
             "max_order_value": "199.99", "delivery_charge": "25.00"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        slab_id = created.data["id"]

        patched = self.client.patch(
            f"{list_url}{slab_id}/", {"delivery_charge": "15.00"}, format="json"
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)

        deleted = self.client.delete(f"{list_url}{slab_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_invalid_slab_range_returns_400(self):
        response = self.client.post(
            "/api/v1/store-settings/delivery-slabs/",
            {"name": "Bad", "min_order_value": "500.00",
             "max_order_value": "100.00", "delivery_charge": "10.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_holiday_crud_and_duplicate(self):
        list_url = "/api/v1/store-settings/holidays/"
        today = str(timezone.localdate())
        created = self.client.post(list_url, {"date": today, "reason": "Festival"},
                                   format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        duplicate = self.client.post(list_url, {"date": today, "reason": "Again"},
                                     format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

        deleted = self.client.delete(f"{list_url}{created.data['id']}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_resolve_slab_endpoint(self):
        make_store(delivery_charge=Decimal("40"),
                   free_delivery_threshold=Decimal("5000"))
        make_delivery_slab(name="Resolver", min_order_value=Decimal("0"),
                           max_order_value=Decimal("999"), delivery_charge=Decimal("12"))
        response = self.client.get(
            "/api/v1/store-settings/delivery-slabs/resolve/?subtotal=100"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["delivery_charge"]), Decimal("12.00"))
