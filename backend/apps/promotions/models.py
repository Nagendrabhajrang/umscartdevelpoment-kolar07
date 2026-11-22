"""Promotions, offers and coupon codes.

A single :class:`Promotion` model covers both automatic offers (no code) and
customer-entered coupons (``code`` set). One rule table keeps validation,
discount arithmetic and reporting in a single place instead of duplicating the
same fields across two models.

:class:`CouponRedemption` records every successful use so per-customer limits
and total usage caps are enforceable and auditable.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.promotions.validators import validate_not_fully_used, validate_promotion_window
from common.models import BaseModel
from common.utils import round_money, unique_reference


class DiscountType(models.TextChoices):
    PERCENTAGE = "percentage", "Percentage discount"
    FIXED = "fixed_amount", "Flat amount discount"
    FREE_DELIVERY = "free_delivery", "Free delivery"


class AppliesTo(models.TextChoices):
    ALL = "all", "All products"
    CATEGORY = "category", "Specific category"
    PRODUCTS = "products", "Specific products"


class Promotion(BaseModel):
    """An offer or coupon code."""

    name = models.CharField(max_length=150)
    code = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Coupon code. Leave empty for an automatic (code-less) offer.",
    )
    description = models.TextField(blank=True, default="")

    discount_type = models.CharField(
        max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Percentage (0-100) or flat amount, depending on discount_type.",
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Cap for percentage discounts. Empty = uncapped.",
    )

    min_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    min_item_quantity = models.PositiveIntegerField(default=0)

    applies_to = models.CharField(
        max_length=20, choices=AppliesTo.choices, default=AppliesTo.ALL
    )
    category = models.ForeignKey(
        "catalog.Category",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="promotions",
    )
    products = models.ManyToManyField(
        "catalog.Product",
        blank=True,
        related_name="promotions",
    )

    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    usage_limit_total = models.PositiveIntegerField(
        null=True, blank=True, help_text="Total redemptions allowed. Empty = unlimited."
    )
    usage_limit_per_customer = models.PositiveIntegerField(
        default=1, help_text="Redemptions allowed per customer."
    )
    used_count = models.PositiveIntegerField(default=0)

    first_order_only = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    is_visible = models.BooleanField(
        default=True, help_text="Show the offer on the storefront."
    )
    priority = models.PositiveIntegerField(
        default=0, help_text="Higher priority promotions are evaluated first."
    )
    display_order = models.PositiveIntegerField(default=0)

    class Meta(BaseModel.Meta):
        db_table = "promotions_promotion"
        verbose_name = "Promotion"
        verbose_name_plural = "Promotions"
        ordering = ("-priority", "display_order", "name")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(discount_value__gte=0),
                name="promotion_discount_value_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(used_count__gte=0), name="promotion_used_count_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(start_date__isnull=True)
                | models.Q(end_date__gt=models.F("start_date")),
                name="promotion_end_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(applies_to=AppliesTo.ALL) | models.Q(category__isnull=False)
                | models.Q(applies_to=AppliesTo.PRODUCTS),
                name="promotion_target_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=["is_active", "start_date", "end_date"], name="idx_promo_active_window"),
            models.Index(fields=["code", "is_active"], name="idx_promo_code_active"),
        ]

    def __str__(self) -> str:
        suffix = f" ({self.code})" if self.code else " (auto)"
        return f"{self.name}{suffix}"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
            self.full_clean(exclude=["uid", "created_at", "updated_at"])
        super().save(*args, **kwargs)

    # --- convenience / domain helpers -------------------------------------
    @property
    def is_coupon(self) -> bool:
        return bool(self.code)

    @property
    def is_currently_valid(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        if self.usage_limit_total is not None and self.used_count >= self.usage_limit_total:
            return False
        return True

    @property
    def remaining_uses(self):
        if self.usage_limit_total is None:
            return None
        return max(0, self.usage_limit_total - self.used_count)

    @property
    def discount_label(self) -> str:
        value = f"{round_money(self.discount_value).normalize():f}"
        if self.discount_type == DiscountType.PERCENTAGE:
            return f"{value}% off"
        if self.discount_type == DiscountType.FIXED:
            return f"₹{value} off"
        return "Free delivery"

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}
        if self.discount_type == DiscountType.PERCENTAGE and self.discount_value > 100:
            errors["discount_value"] = "Percentage discount cannot exceed 100."
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            errors["end_date"] = "End date must be after the start date."
        if self.applies_to == AppliesTo.CATEGORY and not self.category_id:
            errors["category"] = "A category is required when applies_to is 'category'."
        if errors:
            raise ValidationError(errors)


class CouponRedemption(BaseModel):
    """One successful use of a promotion/coupon by a customer on an order."""

    promotion = models.ForeignKey(
        Promotion, on_delete=models.CASCADE, related_name="redemptions"
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="coupon_redemptions"
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupon_redemptions",
    )
    reference = models.CharField(
        max_length=40, unique=True, db_index=True, editable=False
    )
    code_snapshot = models.CharField(max_length=40, blank=True, default="")
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    redeemed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta(BaseModel.Meta):
        db_table = "promotions_redemption"
        verbose_name = "Coupon redemption"
        verbose_name_plural = "Coupon redemptions"
        ordering = ("-redeemed_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["promotion", "order"],
                condition=models.Q(order__isnull=False),
                name="unique_promotion_per_order",
            ),
        ]
        indexes = [
            models.Index(fields=["promotion", "customer"], name="idx_redemption_promo_customer"),
        ]

    def __str__(self) -> str:
        return f"{self.code_snapshot or self.promotion_id} -> customer {self.customer_id}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = unique_reference(CouponRedemption, "reference", "CPN", 6)
        super().save(*args, **kwargs)

    @property
    def is_active_coupon(self) -> bool:
        return validate_not_fully_used(self.promotion) and validate_promotion_window(
            self.promotion
        )
