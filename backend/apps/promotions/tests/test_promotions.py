"""Promotions: discount arithmetic, eligibility rules and redemption limits."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.promotions.models import (
    AppliesTo,
    CouponRedemption,
    DiscountType,
    Promotion,
)
from apps.promotions.services import (
    evaluate_coupon,
    find_best_automatic_promotion,
    get_promotion_by_code,
    redeem_promotion,
    release_redemption,
)
from common.exceptions import BusinessRuleError
from common.tests.factories import make_category, make_customer, make_product


class PromotionModelTests(TestCase):
    def test_code_is_uppercased(self):
        promotion = Promotion.objects.create(
            name="Upper", code="lower", discount_type=DiscountType.FIXED,
            discount_value=Decimal("10"), applies_to=AppliesTo.ALL,
        )
        self.assertEqual(promotion.code, "LOWER")

    def test_code_is_unique(self):
        """save() runs full_clean(), so a duplicate is refused with a
        ValidationError rather than reaching the DB unique index."""
        from django.core.exceptions import ValidationError

        Promotion.objects.create(name="A", code="SAME",
                                 discount_type=DiscountType.FIXED,
                                 discount_value=Decimal("1"),
                                 applies_to=AppliesTo.ALL)
        with self.assertRaises(ValidationError):
            Promotion.objects.create(name="B", code="SAME",
                                     discount_type=DiscountType.FIXED,
                                     discount_value=Decimal("1"),
                                     applies_to=AppliesTo.ALL)

    def test_code_unique_constraint_exists_in_db(self):
        """The database index backs up the application-level check."""
        field = Promotion._meta.get_field("code")
        self.assertTrue(field.unique)

    def test_percentage_cannot_exceed_100(self):
        from django.core.exceptions import ValidationError

        promotion = Promotion(
            name="Too much", code="TOOMUCH",
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("150"), applies_to=AppliesTo.ALL,
        )
        with self.assertRaises(ValidationError):
            promotion.clean()

    def test_end_date_must_be_after_start_date(self):
        from django.core.exceptions import ValidationError

        now = timezone.now()
        promotion = Promotion(
            name="Backwards", code="BACK",
            discount_type=DiscountType.FIXED, discount_value=Decimal("1"),
            applies_to=AppliesTo.ALL,
            start_date=now, end_date=now - timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            promotion.clean()

    def test_is_currently_valid_window(self):
        now = timezone.now()
        future = Promotion.objects.create(
            name="Future", code="FUT",
            discount_type=DiscountType.FIXED, discount_value=Decimal("1"),
            applies_to=AppliesTo.ALL, start_date=now + timedelta(days=1),
        )
        self.assertFalse(future.is_currently_valid)

        expired = Promotion.objects.create(
            name="Expired", code="EXP",
            discount_type=DiscountType.FIXED, discount_value=Decimal("1"),
            applies_to=AppliesTo.ALL, end_date=now - timedelta(days=1),
        )
        self.assertFalse(expired.is_currently_valid)

    def test_remaining_uses(self):
        promotion = Promotion.objects.create(
            name="Limited", code="LIM",
            discount_type=DiscountType.FIXED, discount_value=Decimal("1"),
            applies_to=AppliesTo.ALL, usage_limit_total=10, used_count=3,
        )
        self.assertEqual(promotion.remaining_uses, 7)

    def test_unlimited_remaining_uses_is_none(self):
        promotion = Promotion.objects.create(
            name="Unlimited", code="UNL",
            discount_type=DiscountType.FIXED, discount_value=Decimal("1"),
            applies_to=AppliesTo.ALL,
        )
        self.assertIsNone(promotion.remaining_uses)

    def test_discount_label(self):
        promotion = Promotion.objects.create(
            name="Label", code="LBL",
            discount_type=DiscountType.PERCENTAGE, discount_value=Decimal("15"),
            applies_to=AppliesTo.ALL,
        )
        self.assertIn("15", promotion.discount_label)
        self.assertIn("%", promotion.discount_label)


class FakeItem:
    """Minimal cart-item stand-in for the pure discount engine."""

    def __init__(self, product, quantity, price):
        self.product = product
        self.product_id = product.pk
        self.quantity = quantity
        self.line_total = Decimal(str(price)) * quantity


class DiscountEngineTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.category = make_category(name="Engine Category")
        self.product = make_product(category=self.category, quantity=100,
                                    mrp=Decimal("100"), selling_price=Decimal("100"))
        self.items = [FakeItem(self.product, 5, Decimal("100"))]  # 500 subtotal

    def test_percentage_discount(self):
        promotion = Promotion.objects.create(
            name="P10", code="P10", discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("10"), applies_to=AppliesTo.ALL,
        )
        result = evaluate_coupon("P10", self.customer, self.items, Decimal("500"))
        self.assertTrue(result.applied)
        self.assertEqual(result.discount_amount, Decimal("50.00"))

    def test_percentage_cap(self):
        Promotion.objects.create(
            name="P50", code="P50", discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("50"), max_discount_amount=Decimal("100"),
            applies_to=AppliesTo.ALL,
        )
        result = evaluate_coupon("P50", self.customer, self.items, Decimal("500"))
        self.assertEqual(result.discount_amount, Decimal("100.00"))

    def test_fixed_discount_is_capped_at_subtotal(self):
        Promotion.objects.create(
            name="Big flat", code="BIGFLAT", discount_type=DiscountType.FIXED,
            discount_value=Decimal("900"), applies_to=AppliesTo.ALL,
        )
        result = evaluate_coupon("BIGFLAT", self.customer, self.items, Decimal("500"))
        self.assertEqual(result.discount_amount, Decimal("500.00"))

    def test_free_delivery_flag(self):
        Promotion.objects.create(
            name="Free ship", code="SHIP", discount_type=DiscountType.FREE_DELIVERY,
            discount_value=Decimal("0"), applies_to=AppliesTo.ALL,
        )
        result = evaluate_coupon("SHIP", self.customer, self.items, Decimal("500"))
        self.assertTrue(result.applied)
        self.assertTrue(result.free_delivery)
        self.assertEqual(result.discount_amount, Decimal("0.00"))

    def test_min_order_value_blocks(self):
        Promotion.objects.create(
            name="Min 1000", code="MIN1000", discount_type=DiscountType.FIXED,
            discount_value=Decimal("50"), min_order_value=Decimal("1000"),
            applies_to=AppliesTo.ALL,
        )
        result = evaluate_coupon("MIN1000", self.customer, self.items, Decimal("500"))
        self.assertFalse(result.applied)

    def test_min_item_quantity_blocks(self):
        Promotion.objects.create(
            name="Need 10", code="NEED10", discount_type=DiscountType.FIXED,
            discount_value=Decimal("50"), min_item_quantity=10,
            applies_to=AppliesTo.ALL,
        )
        result = evaluate_coupon("NEED10", self.customer, self.items, Decimal("500"))
        self.assertFalse(result.applied)

    def test_category_targeting(self):
        other_category = make_category(name="Other Cat")
        other_product = make_product(category=other_category, quantity=10)
        mixed_items = self.items + [FakeItem(other_product, 1, Decimal("100"))]

        Promotion.objects.create(
            name="Cat only", code="CATONLY", discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("10"), applies_to=AppliesTo.CATEGORY,
            category=other_category,
        )
        result = evaluate_coupon("CATONLY", self.customer, mixed_items,
                                 Decimal("600"))
        self.assertTrue(result.applied)
        # Only the ₹100 in the targeted category is discounted.
        self.assertEqual(result.discount_amount, Decimal("10.00"))

    def test_product_targeting(self):
        promotion = Promotion.objects.create(
            name="Product only", code="PRODONLY",
            discount_type=DiscountType.FIXED, discount_value=Decimal("25"),
            applies_to=AppliesTo.PRODUCTS,
        )
        promotion.products.add(self.product)
        result = evaluate_coupon("PRODONLY", self.customer, self.items, Decimal("500"))
        self.assertEqual(result.discount_amount, Decimal("25.00"))

    def test_no_matching_items_rejects(self):
        other = make_product(quantity=5, mrp=Decimal("10"), selling_price=Decimal("10"))
        promotion = Promotion.objects.create(
            name="Other product", code="OTHERP", discount_type=DiscountType.FIXED,
            discount_value=Decimal("10"), applies_to=AppliesTo.PRODUCTS,
        )
        promotion.products.add(other)
        result = evaluate_coupon("OTHERP", self.customer, self.items, Decimal("500"))
        self.assertFalse(result.applied)

    def test_unknown_code_is_rejected(self):
        result = evaluate_coupon("NOPE", self.customer, self.items, Decimal("500"))
        self.assertFalse(result.applied)

    def test_inactive_promotion_is_rejected(self):
        Promotion.objects.create(
            name="Off", code="OFF", discount_type=DiscountType.FIXED,
            discount_value=Decimal("10"), applies_to=AppliesTo.ALL, is_active=False,
        )
        result = evaluate_coupon("OFF", self.customer, self.items, Decimal("500"))
        self.assertFalse(result.applied)

    def test_per_customer_limit_blocks(self):
        promotion = Promotion.objects.create(
            name="Once", code="ONCEENG", discount_type=DiscountType.FIXED,
            discount_value=Decimal("10"), applies_to=AppliesTo.ALL,
            usage_limit_per_customer=1,
        )
        CouponRedemption.objects.create(
            promotion=promotion, customer=self.customer,
            discount_amount=Decimal("10"),
        )
        result = evaluate_coupon("ONCEENG", self.customer, self.items, Decimal("500"))
        self.assertFalse(result.applied)

    def test_best_automatic_promotion_wins(self):
        Promotion.objects.create(
            name="Auto 5", discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("5"), applies_to=AppliesTo.ALL, priority=1,
            code=None,
        )
        Promotion.objects.create(
            name="Auto 15", discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("15"), applies_to=AppliesTo.ALL, priority=5,
            code=None,
        )
        best = find_best_automatic_promotion(self.customer, self.items, Decimal("500"))
        self.assertTrue(best.applied)
        self.assertEqual(best.discount_amount, Decimal("75.00"))

    def test_no_automatic_promotion_returns_empty_result(self):
        best = find_best_automatic_promotion(self.customer, self.items, Decimal("500"))
        self.assertFalse(best.applied)


class RedemptionTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.promotion = Promotion.objects.create(
            name="Redeem", code="REDEEM", discount_type=DiscountType.FIXED,
            discount_value=Decimal("10"), applies_to=AppliesTo.ALL,
            usage_limit_total=2, usage_limit_per_customer=1,
        )

    def test_redemption_increments_used_count(self):
        redemption = redeem_promotion(self.promotion, customer=self.customer,
                                      discount_amount=Decimal("10"))
        self.promotion.refresh_from_db()
        self.assertEqual(self.promotion.used_count, 1)
        self.assertEqual(redemption.code_snapshot, "REDEEM")

    def test_per_customer_limit_enforced_tree(self):
        redeem_promotion(self.promotion, customer=self.customer,
                         discount_amount=Decimal("10"))
        with self.assertRaises(BusinessRuleError) as ctx:
            redeem_promotion(self.promotion, customer=self.customer,
                             discount_amount=Decimal("10"))
        self.assertEqual(ctx.exception.code, "promotion_customer_limit_reached")

    def test_total_usage_limit_enforced(self):
        promotion = Promotion.objects.create(
            name="Tiny", code="TINY", discount_type=DiscountType.FIXED,
            discount_value=Decimal("1"), applies_to=AppliesTo.ALL,
            usage_limit_total=1, usage_limit_per_customer=5,
        )
        other = make_customer()
        redeem_promotion(promotion, customer=other, discount_amount=Decimal("1"))
        third = make_customer()
        with self.assertRaises(BusinessRuleError) as ctx:
            redeem_promotion(promotion, customer=third, discount_amount=Decimal("1"))
        self.assertEqual(ctx.exception.code, "promotion_usage_exhausted")

    def test_release_redemption_decrements(self):
        redemption = redeem_promotion(self.promotion, customer=self.customer,
                                      discount_amount=Decimal("10"))
        release_redemption(redemption)
        self.promotion.refresh_from_db()
        self.assertEqual(self.promotion.used_count, 0)
        self.assertFalse(CouponRedemption.objects.filter(pk=redemption.pk).exists())


class PromotionAPITests(APITestCase):
    url = "/api/v1/promotions/"

    def _payload(self, **overrides):
        payload = {
            "name": "API Promo",
            "code": "APIPROMO",
            "discount_type": "percentage",
            "discount_value": "10.00",
            "applies_to": "all",
        }
        payload.update(overrides)
        return payload

    def test_create_promotion(self):
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["code"], "APIPROMO")

    def test_duplicate_code_returns_409(self):
        self.client.post(self.url, self._payload(), format="json")
        response = self.client.post(self.url, self._payload(name="Dup"), format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "duplicate_coupon_code")

    def test_percentage_over_100_returns_400(self):
        response = self.client.post(
            self.url, self._payload(discount_value="150.00"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_category_requires_category_id(self):
        response = self.client.post(
            self.url, self._payload(applies_to="category"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_products_scope_requires_products(self):
        response = self.client.post(
            self.url, self._payload(applies_to="products"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_coupon_code_format(self):
        response = self.client.post(
            self.url, self._payload(code="bad code!"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_filters(self):
        self.client.post(self.url, self._payload(code="FILTER1"), format="json")
        self.client.post(self.url, self._payload(code=None, name="Auto", ), format="json")
        coupons = self.client.get(self.url + "?kind=coupon")
        self.assertEqual(coupons.data["count"], 1)
        automatic = self.client.get(self.url + "?kind=automatic")
        self.assertEqual(automatic.data["count"], 1)

    def test_toggle_endpoint(self):
        created = self.client.post(self.url, self._payload(code="TOGGLE1"), format="json")
        response = self.client.post(
            f"{self.url}{created.data['id']}/toggle/", {"is_active": False}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

    def test_summary_endpoint(self):
        response = self.client.get(f"{self.url}summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total", response.data)

    def test_active_offers_endpoint(self):
        self.client.post(self.url, self._payload(code="VISIBLE1"), format="json")
        response = self.client.get(f"{self.url}active-offers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_delete_promotion(self):
        created = self.client.post(self.url, self._payload(code="DELETE1"),
                                   format="json")
        response = self.client.delete(f"{self.url}{created.data['id']}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_lookup_by_code(self):
        created = self.client.post(self.url, self._payload(code="BYCODE"),
                                   format="json")
        response = self.client.get(f"{self.url}BYCODE/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], created.data["id"])
