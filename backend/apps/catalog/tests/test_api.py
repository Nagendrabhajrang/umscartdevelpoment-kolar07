"""CRUD, filtering, pagination and validation tests for the catalog API."""

from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
from common.tests.factories import make_category, make_child_category, make_product

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00"
    b"\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class CategoryAPITests(APITestCase):
    url = "/api/v1/catalog/categories/"

    def test_create_parent_category(self):
        response = self.client.post(self.url, {"name": "Beverages"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["slug"], "beverages")
        self.assertIsNone(response.data["parent"])

    def test_create_child_category(self):
        parent = make_category(name="Parent")
        response = self.client.post(
            self.url, {"name": "Child", "parent": parent.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["parent"], parent.pk)

    def test_duplicate_name_same_parent_returns_409(self):
        parent = make_category(name="Parent")
        make_child_category(parent=parent, name="Child")
        response = self.client.post(
            self.url, {"name": "Child", "parent": parent.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "duplicate_category")

    def test_third_level_category_returns_400(self):
        parent = make_category(name="L1")
        child = make_child_category(parent=parent, name="L2")
        response = self.client.post(
            self.url, {"name": "L3", "parent": child.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_short_name_returns_400(self):
        response = self.client.post(self.url, {"name": "A"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_pagination_and_filters(self):
        for index in range(4):
            make_category(name=f"Cat {index}")
        response = self.client.get(self.url + "?page_size=2")
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 2)

        only_parents = self.client.get(self.url + "?only_parents=true")
        self.assertEqual(only_parents.data["count"], 4)

    def test_tree_endpoint_returns_nested_children(self):
        parent = make_category(name="Tree Parent")
        make_child_category(parent=parent, name="Tree Child")
        response = self.client.get(self.url + "tree/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        node = next(item for item in response.data if item["id"] == parent.pk)
        self.assertEqual(len(node["children"]), 1)

    def test_update_and_delete(self):
        category = make_category(name="Rename Me")
        patched = self.client.patch(
            f"{self.url}{category.pk}/", {"description": "Updated"}, format="json"
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)

        deleted = self.client.delete(f"{self.url}{category.pk}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_category_with_products_returns_409(self):
        product = make_product()
        response = self.client.delete(f"{self.url}{product.category_id}/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "category_has_products")

    def test_delete_category_with_children_returns_409(self):
        parent = make_category(name="Has Child")
        make_child_category(parent=parent, name="The Child")
        response = self.client.delete(f"{self.url}{parent.pk}/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "category_has_children")


class ProductAPITests(APITestCase):
    url = "/api/v1/catalog/products/"

    def setUp(self):
        self.category = make_category(name="Groceries")

    def _payload(self, **overrides):
        payload = {
            "name": "Test Rice 5kg",
            "category": self.category.pk,
            "mrp": "500.00",
            "selling_price": "450.00",
        }
        payload.update(overrides)
        return payload

    def test_create_product_generates_sku_slug_and_stock_row(self):
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["sku"].startswith("SKU-"))
        self.assertEqual(response.data["slug"], "test-rice-5kg")
        product = Product.objects.get(pk=response.data["id"])
        self.assertIsNotNone(product.stock)

    def test_create_with_initial_quantity_sets_stock(self):
        response = self.client.post(
            self.url, self._payload(initial_quantity=17), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        product = Product.objects.get(pk=response.data["id"])
        self.assertEqual(product.stock.quantity, 17)

    def test_selling_price_above_mrp_returns_400(self):
        response = self.client.post(
            self.url, self._payload(mrp="100.00", selling_price="200.00"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_sku_returns_409(self):
        self.client.post(self.url, self._payload(sku="DUP-1", name="First"), format="json")
        response = self.client.post(
            self.url, self._payload(sku="DUP-1", name="Second"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "duplicate_sku")

    def test_duplicate_barcode_returns_409(self):
        self.client.post(self.url, self._payload(barcode="111", name="First"), format="json")
        response = self.client.post(
            self.url, self._payload(barcode="111", name="Second"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_missing_required_fields_returns_400(self):
        response = self.client.post(self.url, {"name": "No Price"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("details", response.data["error"])

    def test_search_brand_and_price_filters(self):
        make_product(category=self.category, name="Premium Atta", brand="Aashirvaad",
                     mrp=Decimal("300"), selling_price=Decimal("250"))
        make_product(category=self.category, name="Cheap Dal", brand="Local",
                     mrp=Decimal("100"), selling_price=Decimal("90"))

        by_search = self.client.get(self.url + "?search=Premium")
        self.assertEqual(by_search.data["count"], 1)

        by_brand = self.client.get(self.url + "?brand=Aashirvaad")
        self.assertEqual(by_brand.data["count"], 1)

        by_price = self.client.get(self.url + "?min_price=200&max_price=300")
        self.assertEqual(by_price.data["count"], 1)

    def test_category_filter_includes_child_categories(self):
        child = make_child_category(parent=self.category, name="Rice")
        make_product(category=child, name="Child Product")
        response = self.client.get(f"{self.url}?category={self.category.pk}")
        self.assertGreaterEqual(response.data["count"], 1)

    def test_in_stock_filter(self):
        make_product(category=self.category, name="In Stock", quantity=10)
        make_product(category=self.category, name="Out Stock", quantity=0)
        response = self.client.get(self.url + "?in_stock=true")
        self.assertEqual(response.data["count"], 1)

    def test_price_ordering(self):
        make_product(category=self.category, name="P1", mrp=Decimal("100"),
                     selling_price=Decimal("90"))
        make_product(category=self.category, name="P2", mrp=Decimal("300"),
                     selling_price=Decimal("200"))
        response = self.client.get(self.url + "?ordering=-selling_price")
        prices = [Decimal(item["selling_price"]) for item in response.data["results"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_featured_endpoint(self):
        make_product(category=self.category, name="Featured One", is_featured=True)
        response = self.client.get(self.url + "featured/?limit=5")
        self.assertEqual(len(response.data), 1)

    def test_related_endpoint_excludes_self(self):
        product = make_product(category=self.category, name="Main")
        make_product(category=self.category, name="Sibling")
        response = self.client.get(f"{self.url}{product.pk}/related/")
        ids = [item["id"] for item in response.data]
        self.assertNotIn(product.pk, ids)
        self.assertTrue(ids)

    def test_status_action_and_validation(self):
        product = make_product(category=self.category)
        ok = self.client.post(
            f"{self.url}{product.pk}/status/", {"status": "inactive"}, format="json"
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        bad = self.client.post(
            f"{self.url}{product.pk}/status/", {"status": "nonsense"}, format="json"
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_gallery_image_upload_and_delete(self):
        product = make_product(category=self.category)
        upload = SimpleUploadedFile("gal.png", PNG_BYTES, content_type="image/png")
        created = self.client.post(
            f"{self.url}{product.pk}/images/",
            {"image": upload, "alt_text": "Gallery", "is_primary": True},
            format="multipart",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        image_id = created.data["id"]

        listed = self.client.get(f"{self.url}{product.pk}/images/")
        self.assertEqual(len(listed.data), 1)

        deleted = self.client.delete(f"{self.url}{product.pk}/images/{image_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_invalid_image_extension_rejected(self):
        product = make_product(category=self.category)
        upload = SimpleUploadedFile("evil.exe", b"bad", content_type="application/octet-stream")
        response = self.client.post(
            f"{self.url}{product.pk}/images/", {"image": upload}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_delete_removes_from_listing(self):
        product = make_product(category=self.category)
        deleted = self.client.delete(f"{self.url}{product.pk}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get(f"{self.url}{product.pk}/").status_code, 404)
        self.assertEqual(self.client.get(self.url).data["count"], 0)
