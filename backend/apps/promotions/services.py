"""Promotion business logic: validation, discount calculation and redemption.

The discount engine is intentionally pure where possible: given a cart-like
object (anything exposing ``items`` with ``product``, ``quantity`` and
``line_total``) it returns a :class:`DiscountResult` without touching the DB.
Only :func:`redeem_promotion` writes, and it does so under a row lock.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.promotions.models import (
    AppliesTo,
    CouponRedemption,
    DiscountType,
    Promotion,
)
from common.exceptions import BusinessRuleError, ResourceNotFoundError
from common.utils import round_money

logger = logging.getLogger("apps.promotions")

ZERO = Decimal("0.00")


@dataclass
class DiscountResult:
    """Outcome of evaluating a promotion against a cart."""

    promotion: Promotion | None = None
    discount_amount: Decimal = ZERO
    free_delivery: bool = False
    eligible_subtotal: Decimal = ZERO
    message: str = ""
    details: dict = field(default_factory=dict)

    @property
    def applied(self) -> bool:
        return self.promotion is not None and (
            self.discount_amount > 0 or self.free_delivery
        )

    def as_dict(self) -> dict:
        return {
            "promotion_id": self.promotion.id if self.promotion else None,
            "promotion_name": self.promotion.name if self.promotion else None,
            "code": self.promotion.code if self.promotion else None,
            "discount_amount": str(round_money(self.discount_amount)),
            "free_delivery": self.free_delivery,
            "eligible_subtotal": str(round_money(self.eligible_subtotal)),
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def get_promotion_or_404(identifier) -> Promotion:
    from apps.promotions.selectors import get_promotion

    promotion = get_promotion(identifier)
    if promotion is None:
        raise ResourceNotFoundError(
            message=f"Promotion '{identifier}' was not found.",
            code="promotion_not_found",
        )
    return promotion


def get_promotion_by_code(code: str) -> Promotion | None:
    if not code:
        return None
    return Promotion.objects.filter(code__iexact=str(code).strip()).first()


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------
def _promotion_targets_items(promotion: Promotion, items) -> list:
    """Return the cart items a promotion applies to."""
    if promotion.applies_to == AppliesTo.ALL:
        return list(items)
    if promotion.applies_to == AppliesTo.CATEGORY and promotion.category_id:
        from apps.catalog.selectors import get_descendant_ids

        category_ids = get_descendant_ids(promotion.category)
        return [item for item in items if item.product.category_id in category_ids]
    if promotion.applies_to == AppliesTo.PRODUCTS:
        product_ids = set(promotion.products.values_list("id", flat=True))
        return [item for item in items if item.product_id in product_ids]
    return []


def validate_promotion_for_customer(promotion: Promotion, customer, items,
                                    subtotal) -> DiscountResult:
    """Check every business rule and return the resulting discount."""
    result = DiscountResult(promotion=promotion, eligible_subtotal=ZERO)

    if not promotion.is_active:
        result.message = "This promotion is not active."
        return _reject(result)

    if not promotion.is_currently_valid:
        now = timezone.now()
        if promotion.start_date and promotion.start_date > now:
            result.message = f"This promotion starts on {promotion.start_date:%d %b %Y}."
        elif promotion.end_date and promotion.end_date < now:
            result.message = "This promotion has expired."
        else:
            result.message = "This promotion is no longer available."
        return _reject(result)

    if promotion.min_order_value and subtotal < promotion.min_order_value:
        result.message = (
            f"Add items worth ₹{round_money(promotion.min_order_value - subtotal)} "
            f"more to use this promotion (minimum order ₹{promotion.min_order_value})."
        )
        return _reject(result)

    if promotion.min_item_quantity:
        total_quantity = sum(item.quantity for item in items)
        if total_quantity < promotion.min_item_quantity:
            result.message = (
                f"Add at least {promotion.min_item_quantity} item(s) to use this promotion."
            )
            return _reject(result)

    if promotion.first_order_only and customer is not None:
        from apps.orders.models import Order

        has_orders = Order.objects.filter(
            customer=customer,
            status__in=[
                "confirmed",
                "processing",
                "packed",
                "out_for_delivery",
                "delivered",
            ],
        ).exists()
        if has_orders:
            result.message = "This promotion is valid on the first order only."
            return _reject(result)

    if customer is not None and promotion.usage_limit_per_customer:
        already = CouponRedemption.objects.filter(
            promotion=promotion, customer=customer
        ).count()
        if already >= promotion.usage_limit_per_customer:
            result.message = (
                "You have already used this promotion the maximum number of times."
            )
            return _reject(result)

    targeted_items = _promotion_targets_items(promotion, items)
    if not targeted_items:
        result.message = "No items in your cart are eligible for this promotion."
        return _reject(result)

    eligible_subtotal = round_money(
        sum((item.line_total for item in targeted_items), ZERO)
    )
    result.eligible_subtotal = eligible_subtotal

    if promotion.discount_type == DiscountType.PERCENTAGE:
        amount = round_money(eligible_subtotal * promotion.discount_value / Decimal("100"))
        if promotion.max_discount_amount is not None:
            amount = min(amount, round_money(promotion.max_discount_amount))
    elif promotion.discount_type == DiscountType.FIXED:
        amount = min(round_money(promotion.discount_value), eligible_subtotal)
    else:  # FREE_DELIVERY
        amount = ZERO
        result.free_delivery = True

    result.discount_amount = amount
    result.message = "Promotion applied."
    result.details = {
        "discount_type": promotion.discount_type,
        "eligible_items": len(targeted_items),
        "eligible_subtotal": str(eligible_subtotal),
    }
    return result


def _reject(result: DiscountResult) -> DiscountResult:
    result.discount_amount = ZERO
    result.free_delivery = False
    return result


def find_best_automatic_promotion(customer, items, subtotal) -> DiscountResult:
    """Pick the highest-value code-less promotion that applies to this cart."""
    best = DiscountResult()
    promotions = (
        Promotion.objects.filter(
            is_active=True, code__isnull=True, applies_to__in=[
                AppliesTo.ALL, AppliesTo.CATEGORY, AppliesTo.PRODUCTS
            ]
        )
        .prefetch_related("products")
        .order_by("-priority")
    )
    for promotion in promotions:
        candidate = validate_promotion_for_customer(
            promotion, customer, items, subtotal
        )
        if not candidate.applied:
            continue
        if _is_better(candidate, best):
            best = candidate
    return best


def _is_better(candidate: DiscountResult, current: DiscountResult) -> bool:
    if candidate.discount_amount != current.discount_amount:
        return candidate.discount_amount > current.discount_amount
    if candidate.free_delivery and not current.free_delivery:
        return True
    if candidate.promotion and current.promotion:
        return candidate.promotion.priority > current.promotion.priority
    return False


def evaluate_coupon(code, customer, items, subtotal) -> DiscountResult:
    """Validate a coupon code against a cart. Never raises for business reasons."""
    promotion = get_promotion_by_code(code)
    if promotion is None:
        return DiscountResult(message=f"Coupon code '{code}' is not valid.")
    if not promotion.is_coupon:
        return DiscountResult(message=f"Coupon code '{code}' is not valid.")
    return validate_promotion_for_customer(promotion, customer, items, subtotal)


# ---------------------------------------------------------------------------
# Redemption
# ---------------------------------------------------------------------------
@transaction.atomic
def redeem_promotion(promotion: Promotion, *, customer, order=None,
                     discount_amount=ZERO) -> CouponRedemption:
    """Atomically record a redemption and increment the usage counter.

    Locks the promotion row so two concurrent checkouts cannot exceed
    ``usage_limit_total``.
    """
    locked = Promotion.objects.select_for_update().get(pk=promotion.pk)

    if locked.usage_limit_total is not None and locked.used_count >= locked.usage_limit_total:
        raise BusinessRuleError(
            message="This promotion has reached its usage limit.",
            code="promotion_usage_exhausted",
            details={"promotion": locked.id},
        )

    if customer is not None and locked.usage_limit_per_customer:
        used = CouponRedemption.objects.filter(
            promotion=locked, customer=customer
        ).count()
        if used >= locked.usage_limit_per_customer:
            raise BusinessRuleError(
                message="You have already used this promotion the maximum number of times.",
                code="promotion_customer_limit_reached",
                details={"promotion": locked.id, "limit": locked.usage_limit_per_customer},
            )

    if order is not None and CouponRedemption.objects.filter(
        promotion=locked, order=order
    ).exists():
        raise BusinessRuleError(
            message="This promotion is already applied to the order.",
            code="promotion_already_redeemed",
        )

    redemption = CouponRedemption.objects.create(
        promotion=locked,
        customer=customer,
        order=order,
        code_snapshot=locked.code or "",
        discount_amount=round_money(discount_amount),
    )
    locked.used_count = locked.used_count + 1
    locked.save(update_fields=["used_count", "updated_at"])

    logger.info(
        "Promotion redeemed promotion=%s customer=%s amount=%s",
        locked.id, getattr(customer, "id", None), discount_amount,
    )
    return redemption


@transaction.atomic
def release_redemption(redemption: CouponRedemption) -> None:
    """Undo a redemption (called when an order is cancelled)."""
    promotion = Promotion.objects.select_for_update().get(pk=redemption.promotion_id)
    promotion.used_count = max(0, promotion.used_count - 1)
    promotion.save(update_fields=["used_count", "updated_at"])
    redemption.delete()
    logger.info("Promotion redemption released promotion=%s", promotion.id)


# ---------------------------------------------------------------------------
# Admin operations
# ---------------------------------------------------------------------------
@transaction.atomic
def create_promotion(**data) -> Promotion:
    products = data.pop("products", None)
    code = data.get("code")
    if code:
        data["code"] = code.strip().upper()
        if Promotion.objects.filter(code__iexact=data["code"]).exists():
            from common.exceptions import ConflictError

            raise ConflictError(
                message="A promotion with this coupon code already exists.",
                code="duplicate_coupon_code",
                details={"code": data["code"]},
            )
    promotion = Promotion(**data)
    promotion.full_clean(exclude=["uid", "created_at", "updated_at", "used_count"])
    promotion.save()
    if products:
        promotion.products.set(products)
    logger.info("Promotion created id=%s code=%s", promotion.id, promotion.code)
    return promotion


@transaction.atomic
def update_promotion(promotion: Promotion, **data) -> Promotion:
    products = data.pop("products", None)
    code = data.get("code")
    if code:
        data["code"] = code.strip().upper()
        if (
            Promotion.objects.filter(code__iexact=data["code"])
            .exclude(pk=promotion.pk)
            .exists()
        ):
            from common.exceptions import ConflictError

            raise ConflictError(
                message="Another promotion already uses this coupon code.",
                code="duplicate_coupon_code",
                details={"code": data["code"]},
            )
    for field_name, value in data.items():
        setattr(promotion, field_name, value)
    promotion.full_clean(exclude=["uid", "created_at", "updated_at"])
    promotion.save()
    if products is not None:
        promotion.products.set(products)
    return promotion


@transaction.atomic
def delete_promotion(promotion: Promotion) -> None:
    promotion.delete()


@transaction.atomic
def toggle_promotion(promotion: Promotion, is_active: bool) -> Promotion:
    promotion.is_active = is_active
    promotion.save(update_fields=["is_active", "updated_at"])
    return promotion
