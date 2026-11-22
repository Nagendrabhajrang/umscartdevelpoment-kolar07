"""Promotion specific validators.

These return booleans (rather than raising) so they can be composed inside both
serializer validation and service logic without exception gymnastics.
"""

from django.utils import timezone


def validate_promotion_window(promotion) -> bool:
    """True when ``now`` falls inside the promotion's active window."""
    now = timezone.now()
    if promotion.start_date and promotion.start_date > now:
        return False
    if promotion.end_date and promotion.end_date < now:
        return False
    return True


def validate_not_fully_used(promotion) -> bool:
    """True when the promotion still has redemptions available."""
    if promotion.usage_limit_total is None:
        return True
    return promotion.used_count < promotion.usage_limit_total


def validate_coupon_code_format(code: str) -> bool:
    """Coupon codes are 3-40 characters of A-Z, 0-9, underscore or hyphen."""
    if not code:
        return False
    cleaned = str(code).strip()
    if not 3 <= len(cleaned) <= 40:
        return False
    return all(char.isalnum() or char in {"_", "-"} for char in cleaned)
