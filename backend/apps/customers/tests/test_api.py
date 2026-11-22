"""CRUD + validation tests for the customers API."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.customers.models import Customer, CustomerStatus
from common.tests.factories import make_customer


class CustomerAPITests(APITestCase):
    def setUp(self):
        self.list_url = "/api/v1/customers/"

    def test_create_customer_returns_201_and_generated_id(self):
        response = self.client.post(
            self.list_url,
            {
                "full_name": "New Customer",
                "mobile_number": "+919333333333",
                "email": "new@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertIn("uid", response.data)
        self.assertEqual(response.data["mobile_number"], "+919333333333")

    def test_create_customer_duplicate_mobile_returns_409(self):
        make_customer(mobile_number="+919444444444")
        response = self.client.post(
            self.list_url,
            {"full_name": "Copy Cat", "mobile_number": "+919444444444"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "duplicate_mobile_number")

    def test_create_customer_duplicate_email_returns_409(self):
        make_customer(email="taken@example.com", mobile_number="+919455555555")
        response = self.client.post(
            self.list_url,
            {"full_name": "Copy Cat", "mobile_number": "+919466666666",
             "email": "taken@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "duplicate_email")

    def test_invalid_mobile_returns_400_with_field_error(self):
        response = self.client.post(
            self.list_url,
            {"full_name": "Bad Mobile", "mobile_number": "abc"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("details", response.data["error"])
        self.assertIn("mobile_number", response.data["error"]["details"])

    def test_short_full_name_returns_400(self):
        response = self.client.post(
            self.list_url,
            {"full_name": "A", "mobile_number": "+919477777777"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_is_paginated(self):
        for index in range(5):
            make_customer(mobile_number=f"+91988000{index:04d}")
        response = self.client.get(self.list_url + "?page_size=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["count"], 5)
        self.assertIn("next", response.data)

    def test_list_search_filter(self):
        make_customer(full_name="Searchable Person", mobile_number="+919900000001")
        make_customer(full_name="Other Person", mobile_number="+919900000002")
        response = self.client.get(self.list_url + "?search=Searchable")
        self.assertEqual(response.data["count"], 1)

    def test_list_status_filter(self):
        make_customer(mobile_number="+919911111111", status=CustomerStatus.BLOCKED)
        make_customer(mobile_number="+919911111112", status=CustomerStatus.ACTIVE)
        response = self.client.get(self.list_url + "?status=blocked")
        self.assertEqual(response.data["count"], 1)

    def test_retrieve_by_id_and_uuid(self):
        customer = make_customer()
        by_id = self.client.get(f"{self.list_url}{customer.pk}/")
        by_uid = self.client.get(f"{self.list_url}{customer.uid}/")
        self.assertEqual(by_id.status_code, status.HTTP_200_OK)
        self.assertEqual(by_uid.status_code, status.HTTP_200_OK)
        self.assertEqual(by_id.data["id"], by_uid.data["id"])

    def test_retrieve_missing_returns_404(self):
        response = self.client.get(f"{self.list_url}999999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "customer_not_found")

    def test_update_and_partial_update(self):
        customer = make_customer(full_name="Before Update")
        response = self.client.patch(
            f"{self.list_url}{customer.pk}/", {"full_name": "After Update"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_name"], "After Update")

    def test_update_to_duplicate_mobile_returns_409(self):
        first = make_customer(mobile_number="+919922222221")
        make_customer(mobile_number="+919922222222")
        response = self.client.patch(
            f"{self.list_url}{first.pk}/", {"mobile_number": "+919922222222"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_status_action(self):
        customer = make_customer()
        response = self.client.post(
            f"{self.list_url}{customer.pk}/status/", {"status": "blocked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        customer.refresh_from_db()
        self.assertEqual(customer.status, CustomerStatus.BLOCKED)

    def test_invalid_status_action_returns_400(self):
        customer = make_customer()
        response = self.client.post(
            f"{self.list_url}{customer.pk}/status/", {"status": "banana"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_notes_endpoint(self):
        customer = make_customer()
        created = self.client.post(
            f"{self.list_url}{customer.pk}/notes/",
            {"note": "Prefers evening delivery"},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        listed = self.client.get(f"{self.list_url}{customer.pk}/notes/")
        self.assertEqual(len(listed.data), 1)

    def test_delete_customer_returns_204(self):
        customer = make_customer()
        response = self.client.delete(f"{self.list_url}{customer.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Customer.objects.filter(pk=customer.pk).exists())

    def test_delete_customer_with_orders_returns_409(self):
        from common.tests.factories import make_address, make_order, make_product

        customer = make_customer()
        address = make_address(customer)
        product = make_product()
        make_order(customer, address=address,
                   items=[{"product": product, "quantity": 1,
                           "unit_price": product.selling_price}])
        response = self.client.delete(f"{self.list_url}{customer.pk}/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "customer_has_orders")

    def test_summary_endpoint(self):
        make_customer(mobile_number="+919933333331")
        response = self.client.get(f"{self.list_url}summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total", response.data)
        self.assertGreaterEqual(response.data["total"], 1)

    def test_method_not_allowed_on_unsupported_verb(self):
        response = self.client.put(self.list_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
