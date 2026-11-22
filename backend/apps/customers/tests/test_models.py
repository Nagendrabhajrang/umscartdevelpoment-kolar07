"""Model + relationship tests for the customers app."""

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.customers.models import Customer, CustomerStatus
from common.tests.factories import make_customer


class CustomerModelTests(TestCase):
    def test_customer_is_created_with_generated_identifiers(self):
        customer = make_customer(full_name="Aarav Sharma")
        self.assertIsNotNone(customer.pk)
        self.assertIsNotNone(customer.uid)
        self.assertEqual(customer.status, CustomerStatus.ACTIVE)
        self.assertTrue(customer.can_order)

    def test_mobile_number_is_normalised_on_save(self):
        customer = Customer(full_name="Space Test", mobile_number="+91 98765-43210")
        customer.save()
        self.assertEqual(customer.mobile_number, "+919876543210")

    def test_mobile_number_is_unique(self):
        make_customer(mobile_number="+919111111111")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Customer.objects.create(
                    full_name="Duplicate", mobile_number="+919111111111"
                )

    def test_email_is_lowercased(self):
        customer = make_customer(email="MiXeD@Example.COM")
        self.assertEqual(customer.email, "mixed@example.com")

    def test_email_may_be_null(self):
        customer = make_customer(email=None)
        self.assertIsNone(customer.email)

    def test_blocked_customer_cannot_order(self):
        customer = make_customer(status=CustomerStatus.BLOCKED)
        self.assertFalse(customer.can_order)

    def test_str_representation(self):
        customer = make_customer(full_name="Diya Patel", mobile_number="+919222222222")
        self.assertIn("Diya Patel", str(customer))
        self.assertIn("+919222222222", str(customer))

    def test_timestamps_are_set(self):
        customer = make_customer()
        self.assertIsNotNone(customer.created_at)
        self.assertIsNotNone(customer.updated_at)

    def test_soft_delete_hides_customer_from_default_manager(self):
        customer = make_customer(full_name="Soft Deleted")
        customer_id = customer.pk
        customer.delete()
        self.assertFalse(Customer.objects.filter(pk=customer_id).exists())
        self.assertTrue(Customer.all_objects.filter(pk=customer_id).exists())

    def test_address_count_and_default_address_properties(self):
        from common.tests.factories import make_address

        customer = make_customer()
        self.assertEqual(customer.address_count, 0)
        self.assertIsNone(customer.default_address)

        address = make_address(customer)
        self.assertEqual(customer.address_count, 1)
        self.assertEqual(customer.default_address, address)
