"""Addresses, wishlist and banners: ownership, defaults and CRUD contracts."""

import io
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.addresses.models import Address, AddressLabel
from apps.addresses.selectors import get_default_address
from apps.addresses.services import create_address, set_default_address
from apps.banners.models import Banner, BannerPlacement
from apps.wishlist.models import Wishlist, WishlistItem
from apps.wishlist.services import (
    add_to_wishlist,
    move_to_cart,
    remove_wishlist_item,
    toggle_wishlist_item,
)
from common.exceptions import BusinessRuleError, ConflictError, InsufficientStockError
from common.tests.factories import make_address, make_customer, make_product, make_store


def _png_bytes():
    """A tiny in-memory PNG for image-upload endpoints."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def _png_upload(name="banner.png"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, _png_bytes(), content_type="image/png")


def _listed(response):
    """Unwrap paginated or plain list responses."""
    data = response.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


class AddressModelTests(TestCase):
    def setUp(self):
        self.customer = make_customer()

    def test_full_address_includes_key_parts(self):
        address = make_address(self.customer)
        self.assertIn("Test", address.full_address)
        self.assertIn("560001", address.full_address)

    def test_first_address_becomes_default(self):
        address = make_address(self.customer)
        self.assertTrue(address.is_default)

    def test_second_address_is_not_default(self):
        make_address(self.customer, label="Home")
        second = make_address(self.customer, label="Work")
        self.assertFalse(second.is_default)

    def test_setting_default_unsets_previous(self):
        first = make_address(self.customer, label="Home")
        second = make_address(self.customer, label="Work")
        set_default_address(second)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)
        self.assertEqual(get_default_address(self.customer).pk, second.pk)

    def test_pincode_validation(self):
        address = Address(
            customer=self.customer, label=AddressLabel.HOME,
            recipient_name="Test", recipient_mobile="9876543210",
            line1="1 Street", city="Bengaluru", state="Karnataka",
            pincode="123",
        )
        with self.assertRaises(ValidationError):
            address.full_clean()

    def test_deleting_default_promotes_another(self):
        first = make_address(self.customer, label="Home")
        second = make_address(self.customer, label="Work")
        # delete via the service so the "promote another" rule runs
        from apps.addresses.services import delete_address

        delete_address(first)
        second.refresh_from_db()
        self.assertTrue(second.is_default)


class AddressAPITests(APITestCase):
    def setUp(self):
        make_store()
        self.customer = make_customer()
        self.headers = {"HTTP_X_CUSTOMER_ID": str(self.customer.pk)}
        self.mine = "/api/v1/addresses/mine/"
        self.add = "/api/v1/addresses/mine/add/"
        self.url = "/api/v1/addresses/"

    def _payload(self, **overrides):
        payload = {
            "label": "home",
            "recipient_name": "Test User",
            "recipient_mobile": "9876543210",
            "line1": "Flat 1, Test Apartments",
            "line2": "Near Park",
            "landmark": "Opposite school",
            "city": "Bengaluru",
            "state": "Karnataka",
            "pincode": "560001",
        }
        payload.update(overrides)
        return payload

    def test_customer_can_add_address(self):
        response = self.client.post(self.add, self._payload(), format="json",
                                    **self.headers)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["is_default"])

    def test_mine_lists_only_own_addresses(self):
        other = make_customer()
        make_address(other)
        self.client.post(self.add, self._payload(), format="json", **self.headers)
        listed = self.client.get(self.mine, **self.headers)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(_listed(listed)), 1)

    def test_customer_header_required(self):
        response = self.client.get(self.mine)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "customer_context_required")

    def test_unknown_customer_returns_404(self):
        response = self.client.get(self.mine, HTTP_X_CUSTOMER_ID="999999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_pincode_returns_400(self):
        response = self.client.post(self.add, self._payload(pincode="ABC"),
                                    format="json", **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_required_field_returns_400(self):
        payload = self._payload()
        payload.pop("line1")
        response = self.client.post(self.add, payload, format="json", **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "validation_error")

    def test_set_default_endpoint(self):
        first = self.client.post(self.add, self._payload(), format="json",
                                 **self.headers)
        second = self.client.post(self.add, self._payload(label="work"),
                                  format="json", **self.headers)
        response = self.client.post(
            f"{self.url}{second.data['id']}/set-default/", {}, format="json",
            **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_default"])

    def test_admin_scope_list_filters_by_customer(self):
        make_address(self.customer)
        other = make_customer()
        make_address(other)
        response = self.client.get(f"{self.url}?customer={other.pk}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(_listed(response)), 1)

    def test_update_address(self):
        created = self.client.post(self.add, self._payload(), format="json",
                                  **self.headers)
        response = self.client.patch(
            f"{self.url}{created.data['id']}/", {"line1": "New Line"},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["line1"], "New Line")

    def test_delete_address(self):
        created = self.client.post(self.add, self._payload(), format="json",
                                  **self.headers)
        response = self.client.delete(f"{self.url}{created.data['id']}/",
                                     **self.headers)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_read_other_customers_address_via_mine(self):
        other = make_customer()
        make_address(other)
        response = self.client.get(self.mine, **self.headers)
        self.assertEqual(len(_listed(response)), 0)

    def test_unknown_address_returns_404(self):
        response = self.client.get(f"{self.url}999999/", **self.headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class WishlistServiceTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.product = make_product(quantity=10)

    def test_default_wishlist_recovers_from_lost_race(self):
        """Two first visits at once must both get the wishlist, not a 500.

        The service's lookup misses, then its INSERT hits the real unique
        constraint because a parallel request already committed the row. The
        recovery read must succeed: the failed INSERT has to be isolated in its
        own atomic block, otherwise the surrounding transaction is poisoned and
        the read raises TransactionManagementError (the live
        /api/v1/wishlist/ 500). The collision is a genuine database error, so
        the broken-transaction behaviour being tested is Django's own.
        """
        from unittest import mock

        from apps.wishlist import services as wishlist_services

        WishlistItem.objects.all().delete()
        Wishlist.objects.filter(customer=self.customer).delete()
        competitor = Wishlist.objects.create(
            customer=self.customer, name="Default", is_default=True
        )
        real_manager = Wishlist.objects
        customer_id = self.customer.id
        state = {"lookups": 0}

        class _Manager:
            def __getattr__(self, name):
                return getattr(real_manager, name)

            def filter(self, *args, **kwargs):
                state["lookups"] += 1
                if state["lookups"] == 1:
                    return real_manager.filter(pk__in=[])   # nothing yet
                return real_manager.filter(*args, **kwargs)

            def create(self, *args, **kwargs):
                # A real INSERT: Postgres raises the unique violation for us.
                state["inserts"] = state.get("inserts", 0) + 1
                return real_manager.create(customer_id=customer_id,
                                           name="Default", is_default=True)

        with mock.patch.object(wishlist_services, "Wishlist") as patched:
            patched.objects = _Manager()
            back = wishlist_services.get_or_create_default_wishlist(self.customer)

        self.assertEqual(state["inserts"], 1)   # tried to create, collided once
        self.assertEqual(back.pk, competitor.pk)

    def test_add_to_wishlist(self):
        item = add_to_wishlist(self.customer, self.product)
        self.assertEqual(item.product, self.product)
        self.assertEqual(WishlistItem.objects.count(), 1)

    def test_duplicate_add_raises_conflict(self):
        add_to_wishlist(self.customer, self.product)
        with self.assertRaises(ConflictError):
            add_to_wishlist(self.customer, self.product)

    def test_remove_wishlist_item(self):
        item = add_to_wishlist(self.customer, self.product)
        remove_wishlist_item(item)
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_toggle_adds_then_removes(self):
        first = toggle_wishlist_item(self.customer, self.product)
        self.assertTrue(first["is_wishlisted"])
        second = toggle_wishlist_item(self.customer, self.product)
        self.assertFalse(second["is_wishlisted"])
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_move_to_cart(self):
        item = add_to_wishlist(self.customer, self.product)
        cart_item = move_to_cart(item, quantity=2)
        self.assertEqual(cart_item.quantity, 2)
        self.assertFalse(WishlistItem.objects.filter(pk=item.pk).exists())

    def test_move_to_cart_keeps_item_when_out_of_stock(self):
        item = add_to_wishlist(self.customer, self.product)
        stock = self.product.stock
        stock.quantity = 0
        stock.save()
        with self.assertRaises(InsufficientStockError):
            move_to_cart(item, quantity=5)
        self.assertTrue(WishlistItem.objects.filter(pk=item.pk).exists())


class WishlistAPITests(APITestCase):
    def setUp(self):
        make_store()
        self.customer = make_customer()
        self.product = make_product(quantity=10, mrp=Decimal("100"),
                                    selling_price=Decimal("90"))
        self.headers = {"HTTP_X_CUSTOMER_ID": str(self.customer.pk)}
        self.items = "/api/v1/wishlist/items/"
        self.mine = "/api/v1/wishlist/"

    def auth(self):
        """A real signed-in customer, obtained through the OTP flow.

        Cached per test: the OTP endpoint has a resend cooldown, so a second
        call inside the same test would be (correctly) refused.

        `/api/v1/wishlist/` and `/wishlist/toggle/` are account endpoints and
        now declare `IsAuthenticated` (round 27), so they need a session rather
        than the legacy X-Customer-Id seam. Signing in for real keeps the test
        honest about how the storefront actually reaches these routes.
        """
        from django.test import override_settings

        cached = getattr(self, "_auth_header", None)
        if cached is not None:
            return cached

        # The code is only echoed when dev mode is on, and dev mode also needs
        # DEBUG; the test runner forces DEBUG off, so state both here.
        with override_settings(AUTH_DEV_MODE=True, DEBUG=True):
            sent = self.client.post(
                "/api/customer/send-otp/",
                {"mobile_number": self.customer.mobile_number},
                format="json",
            )
            self.assertEqual(sent.status_code, 200, sent.data)
            verified = self.client.post(
                "/api/customer/verify-otp/",
                {
                    "mobile_number": self.customer.mobile_number,
                    "code": sent.data["dev_otp"],
                },
                format="json",
            )
        self.assertEqual(verified.status_code, 200, verified.data)
        # Round 30: the login response set the session cookie on this client, so
        # there is no header to carry. Returning an empty mapping keeps every
        # existing `**self.headers` call site working unchanged.
        self._auth_header = {}
        return self._auth_header

    def test_add_item(self):
        response = self.client.post(self.items, {"product": self.product.pk},
                                    format="json", **self.headers)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicate_returns_409(self):
        self.client.post(self.items, {"product": self.product.pk}, format="json",
                         **self.headers)
        response = self.client.post(self.items, {"product": self.product.pk},
                                    format="json", **self.headers)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "duplicate_wishlist_item")

    def test_mine_lists_items(self):
        self.client.post(self.items, {"product": self.product.pk}, format="json",
                         **self.headers)
        response = self.client.get(self.mine, **{**self.headers, **self.auth()})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_add_unknown_product_returns_404(self):
        response = self.client.post(self.items, {"product": 999999}, format="json",
                                    **self.headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_item(self):
        created = self.client.post(self.items, {"product": self.product.pk},
                                   format="json", **self.headers)
        response = self.client.delete(f"{self.items}{created.data['id']}/",
                                      **self.headers)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_toggle_endpoint(self):
        first = self.client.post("/api/v1/wishlist/toggle/",
                                 {"product": self.product.pk}, format="json",
                                 **{**self.headers, **self.auth()})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertTrue(first.data["is_wishlisted"])

        second = self.client.post("/api/v1/wishlist/toggle/",
                                  {"product": self.product.pk}, format="json",
                                  **{**self.headers, **self.auth()})
        self.assertFalse(second.data["is_wishlisted"])

    def test_move_to_cart_endpoint(self):
        created = self.client.post(self.items, {"product": self.product.pk},
                                   format="json", **self.headers)
        response = self.client.post(
            f"{self.items}{created.data['id']}/move-to-cart/", {"quantity": 2},
            format="json", **self.headers,
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_summary_endpoint(self):
        response = self.client.get("/api/v1/wishlist/lists/summary/",
                                   **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BannerModelTests(TestCase):
    def test_display_order_defaults_to_zero(self):
        banner = Banner.objects.create(
            title="Test Banner", placement=BannerPlacement.HERO,
        )
        self.assertEqual(banner.display_order, 0)

    def test_future_banner_is_not_live(self):
        banner = Banner.objects.create(
            title="Future", placement=BannerPlacement.HERO,
            start_date=timezone.now() + timedelta(days=1),
        )
        self.assertFalse(banner.is_live)

    def test_expired_banner_is_not_live(self):
        banner = Banner.objects.create(
            title="Expired", placement=BannerPlacement.HERO,
            end_date=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(banner.is_live)

    def test_live_window_banner_is_live(self):
        banner = Banner.objects.create(
            title="Live", placement=BannerPlacement.HERO,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1),
        )
        self.assertTrue(banner.is_live)

    def test_inactive_banner_not_live(self):
        banner = Banner.objects.create(
            title="Off", placement=BannerPlacement.HERO, is_active=False,
        )
        self.assertFalse(banner.is_live)


class BannerAPITests(APITestCase):
    url = "/api/v1/banners/"

    def test_create_banner(self):
        response = self.client.post(
            self.url,
            {"title": "API Banner", "placement": "hero", "is_active": True,
             "image": _png_upload()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "API Banner")

    def test_banner_without_image_returns_400(self):
        response = self.client.post(
            self.url, {"title": "No image", "placement": "hero"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_title_required(self):
        response = self.client.post(self.url, {"placement": "hero"},
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_returns_banners(self):
        Banner.objects.create(title="Visible", placement=BannerPlacement.HERO)
        Banner.objects.create(title="Hidden", placement=BannerPlacement.HERO,
                              is_active=False)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_placement_filter(self):
        Banner.objects.create(title="Hero", placement=BannerPlacement.HERO)
        Banner.objects.create(title="Strip", placement=BannerPlacement.STRIP)
        response = self.client.get(self.url + "?placement=strip")
        titles = [b["title"] for b in _listed(response)]
        self.assertEqual(titles, ["Strip"])

    def test_live_endpoint_excludes_inactive(self):
        Banner.objects.create(title="Live one", placement=BannerPlacement.HERO)
        Banner.objects.create(title="Off one", placement=BannerPlacement.HERO,
                              is_active=False)
        response = self.client.get(f"{self.url}live/?placement=hero")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in _listed(response)]
        self.assertIn("Live one", titles)
        self.assertNotIn("Off one", titles)

    def test_toggle_endpoint(self):
        created = self.client.post(
            self.url,
            {"title": "Toggle", "placement": "hero", "image": _png_upload()},
            format="multipart",
        )
        response = self.client.post(f"{self.url}{created.data['id']}/toggle/",
                                    {"is_active": False}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

    def test_update_and_delete(self):
        created = self.client.post(
            self.url,
            {"title": "Mutable", "placement": "hero", "image": _png_upload()},
            format="multipart",
        )
        banner_id = created.data["id"]
        patched = self.client.patch(f"{self.url}{banner_id}/",
                                    {"title": "Renamed"}, format="json")
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data["title"], "Renamed")

        deleted = self.client.delete(f"{self.url}{banner_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_unknown_banner_returns_404(self):
        response = self.client.get(f"{self.url}999999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_click_endpoint_increments_counter(self):
        created = self.client.post(
            self.url,
            {"title": "Clickable", "placement": "hero",
             "link_type": "url", "link_url": "https://example.com",
             "image": _png_upload()},
            format="multipart",
        )
        response = self.client.post(f"{self.url}{created.data['id']}/click/",
                                    {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["click_count"], 1)
