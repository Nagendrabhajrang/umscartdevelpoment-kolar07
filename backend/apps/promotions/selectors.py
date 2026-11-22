"""Read-only queries for promotions."""

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.promotions.models import CouponRedemption, Promotion
from common.selectors import id_or_uid_q


def list_promotions(filters: dict | None = None) -> QuerySet[Promotion]:
    queryset = Promotion.objects.select_related("category").prefetch_related("products")
    filters = filters or {}

    if filters.get("is_active") is not None:
        queryset = queryset.filter(is_active=filters["is_active"])
    if filters.get("kind") == "coupon":
        queryset = queryset.filter(code__isnull=False)
    elif filters.get("kind") == "automatic":
        queryset = queryset.filter(code__isnull=True)
    if filters.get("code"):
        queryset = queryset.filter(code__iexact=filters["code"])
    if filters.get("currently_valid"):
        now = timezone.now()
        queryset = queryset.filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now),
            Q(end_date__isnull=True) | Q(end_date__gte=now),
            is_active=True,
        )
    search = filters.get("search")
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(code__icontains=search)
            | Q(description__icontains=search)
        )
    return queryset


def get_promotion(identifier) -> Promotion | None:
    """Fetch by numeric id, public UUID or coupon code."""
    query = id_or_uid_q(identifier)
    if query is not None:
        found = (
            Promotion.objects.select_related("category")
            .prefetch_related("products")
            .filter(query)
            .first()
        )
        if found:
            return found
    if identifier:
        return (
            Promotion.objects.select_related("category")
            .prefetch_related("products")
            .filter(code__iexact=str(identifier))
            .first()
        )
    return None


def list_visible_offers() -> QuerySet[Promotion]:
    """Offers that should be advertised on the storefront."""
    now = timezone.now()
    return (
        Promotion.objects.filter(
            is_active=True,
            is_visible=True,
        )
        .filter(Q(start_date__isnull=True) | Q(start_date__lte=now))
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
        .order_by("-priority", "display_order")
    )


def list_redemptions(filters: dict | None = None) -> QuerySet[CouponRedemption]:
    queryset = CouponRedemption.objects.select_related("promotion", "customer", "order")
    filters = filters or {}
    if filters.get("promotion"):
        queryset = queryset.filter(promotion_id=filters["promotion"])
    if filters.get("customer"):
        queryset = queryset.filter(customer_id=filters["customer"])
    if filters.get("order"):
        queryset = queryset.filter(order_id=filters["order"])
    return queryset


def promotion_summary() -> dict:
    now = timezone.now()
    aggregate = Promotion.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        coupons=Count("id", filter=Q(code__isnull=False)),
        expired=Count("id", filter=Q(end_date__lt=now)),
    )
    aggregate["total_redemptions"] = CouponRedemption.objects.count()
    return aggregate
