"""Model, constraint and relationship tests for the catalog app."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.catalog.models import Category, Product, ProductImage
from common.tests.factories import make_category, make_child_category, make_product


class CategoryModelTests(TestCase):
    def test_slug_is_generated_from_name(self):
        category = make_category(name="Fresh Fruits & Vegetables")
        self.assertEqual(category.slug, "fresh-fruits-vegetables")

    def test_slug_is_unique_across_duplicate_names(self):
        Category.objects.create(name="Dairy")
        second = Category.objects.create(name="Dairy")
        self.assertEqual(second.slug, "dairy-1")

    def test_parent_child_relationship(self):
        parent = make_category(name="Fruits")
        child = make_child_category(parent=parent, name="Citrus")
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())
        self.assertTrue(parent.is_parent)
        self.assertFalse(child.is_parent)

    def test_duplicate_name_under_same_parent_is_rejected(self):
        parent = make_category(name="Grains")
        make_child_category(parent=parent, name="Rice")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(parent=parent, name="Rice")

    def test_category_cannot_be_its_own_parent(self):
        category = make_category()
        category.parent = category
        with self.assertRaises(ValidationError):
            category.clean()

    def test_max_two_levels_enforced_by_clean(self):
        parent = make_category(name="Level1")
        child = make_child_category(parent=parent, name="Level2")
        grandchild = Category(name="Level3", parent=child)
        with self.assertRaises(ValidationError):
            grandchild.clean()

    def test_full_path_and_str(self):
        parent = make_category(name="Snacks")
        child = make_child_category(parent=parent, name="Chips")
        self.assertEqual(str(child), "Snacks > Chips")
        self.assertEqual(parent.full_path, "Snacks")


class ProductModelTests(TestCase):
    def test_sku_is_auto_generated_and_unique(self):
        first = make_product()
        second = make_product()
        self.assertTrue(first.sku.startswith("SKU-"))
        self.assertNotEqual(first.sku, second.sku)

    def test_explicit_sku_is_preserved(self):
        product = make_product(sku="CUSTOM-SKU-1")
        self.assertEqual(product.sku, "CUSTOM-SKU-1")

    def test_sku_unique_constraint(self):
        make_product(sku="UNIQUE-1")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_product(sku="UNIQUE-1")

    def test_selling_price_above_mrp_fails_check_constraint(self):
        category = make_category()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(
                    name="Invalid Price",
                    category=category,
                    mrp=Decimal("10.00"),
                    selling_price=Decimal("20.00"),
                )

    def test_negative_price_fails_check_constraint(self):
        category = make_category()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.create(
                    name="Negative",
                    category=category,
                    mrp=Decimal("-1.00"),
                    selling_price=Decimal("-2.00"),
                )

    def test_discount_percent_and_amount(self):
        product = make_product(mrp=Decimal("100.00"), selling_price=Decimal("80.00"))
        self.assertEqual(product.discount_percent, Decimal("20.00"))
        self.assertEqual(product.discount_amount, Decimal("20.00"))

    def test_zero_discount_when_price_equals_mrp(self):
        product = make_product(mrp=Decimal("50.00"), selling_price=Decimal("50.00"))
        self.assertEqual(product.discount_percent, Decimal("0.00"))

    def test_unit_label(self):
        product = make_product(unit_value=Decimal("500.00"))
        self.assertIn("500", product.unit_label)

    def test_stock_relationship_and_availability(self):
        product = make_product(quantity=7)
        self.assertEqual(product.available_quantity, 7)
        self.assertTrue(product.in_stock)
        self.assertTrue(product.is_purchasable)

    def test_soft_delete_hides_product_but_keeps_row(self):
        product = make_product()
        product.delete()
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        self.assertTrue(Product.all_objects.filter(pk=product.pk).exists())
        self.assertIsNotNone(product.deleted_at)

    def test_category_protect_on_delete(self):
        product = make_product()
        with self.assertRaises(Exception):
            product.category.delete()

    def test_str_representation(self):
        product = make_product(name="Basmati Rice", sku="RICE-1")
        self.assertEqual(str(product), "Basmati Rice [RICE-1]")


class ProductImageModelTests(TestCase):
    def test_only_one_primary_image_per_product(self):
        product = make_product()
        from django.core.files.base import ContentFile

        ProductImage.objects.create(
            product=product,
            image=ContentFile(b"fake", name="a.png"),
            is_primary=True,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductImage.objects.create(
                    product=product,
                    image=ContentFile(b"fake", name="b.png"),
                    is_primary=True,
                )

    def test_cascade_delete_with_product(self):
        product = make_product()
        from django.core.files.base import ContentFile

        ProductImage.objects.create(
            product=product, image=ContentFile(b"fake", name="c.png")
        )
        self.assertEqual(product.images.count(), 1)
        product.delete(hard=True)
        self.assertEqual(ProductImage.objects.count(), 0)
