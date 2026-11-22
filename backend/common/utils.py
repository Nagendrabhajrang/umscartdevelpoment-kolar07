"""Generic helpers shared by services and serializers."""

import random
import string
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone
from django.utils.text import slugify

MONEY_QUANTUM = Decimal("0.01")


def round_money(value) -> Decimal:
    """Round a monetary value to 2 decimal places using commercial rounding."""
    if value is None:
        return Decimal("0.00")
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def money(value) -> str:
    """Serialise an amount as a fixed two-decimal string (JSON safe)."""
    return f"{round_money(value):.2f}"


def percentage_of(amount, percent) -> Decimal:
    """Return ``percent`` % of ``amount`` rounded to two decimals."""
    amount = Decimal(str(amount or 0))
    percent = Decimal(str(percent or 0))
    return round_money(amount * percent / Decimal("100"))


def generate_reference(prefix: str, length: int = 6) -> str:
    """Generate a human friendly, reasonably unique reference.

    Example: ``UMS-20261109-4F7B2K``
    """
    date_part = timezone.localtime().strftime("%Y%m%d")
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{date_part}-{body}"


def unique_reference(model, field: str, prefix: str, length: int = 6, attempts: int = 12) -> str:
    """Generate a reference that is unique for ``model.field``."""
    for _ in range(attempts):
        candidate = generate_reference(prefix, length)
        if not model._default_manager.filter(**{field: candidate}).exists():
            return candidate
    # Extremely unlikely fallback - guarantee uniqueness with a uuid tail.
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def unique_slug(model, value: str, field: str = "slug", max_length: int = 160) -> str:
    """Build a slug for ``model`` that does not collide with existing rows."""
    base = slugify(value)[:max_length] or "item"
    candidate = base
    counter = 1
    while model._default_manager.filter(**{field: candidate}).exists():
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def get_client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def percent_discount(mrp, selling_price) -> Decimal:
    """Discount percentage of ``selling_price`` against ``mrp``."""
    mrp = Decimal(str(mrp or 0))
    selling_price = Decimal(str(selling_price or 0))
    if mrp <= 0 or selling_price >= mrp:
        return Decimal("0.00")
    return round_money((mrp - selling_price) / mrp * Decimal("100"))


def chunked(iterable, size: int):
    """Yield lists of at most ``size`` items from ``iterable``."""
    bucket = []
    for item in iterable:
        bucket.append(item)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket
