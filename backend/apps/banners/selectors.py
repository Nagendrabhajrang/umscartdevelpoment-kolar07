"""Read-only queries for banners."""

from django.db.models import F, Q, QuerySet
from django.utils import timezone

from apps.banners.models import Banner
from common.selectors import id_or_uid_q


def list_banners(filters: dict | None = None) -> QuerySet[Banner]:
    queryset = Banner.objects.select_related("linked_product", "linked_category")
    filters = filters or {}

    placement = filters.get("placement")
    if placement:
        queryset = queryset.filter(placement=placement)
    if filters.get("is_active") is not None:
        queryset = queryset.filter(is_active=filters["is_active"])
    if filters.get("live_only"):
        now = timezone.now()
        queryset = queryset.filter(
            is_active=True,
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now)
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
    search = filters.get("search")
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | Q(subtitle__icontains=search)
        )
    return queryset


def get_banner(identifier) -> Banner | None:
    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return (
        Banner.objects.select_related("linked_product", "linked_category")
        .filter(query)
        .first()
    )


def get_live_banners(placement: str | None = None) -> QuerySet[Banner]:
    return list_banners({"live_only": True, "placement": placement})


def register_view(banner: Banner) -> None:
    Banner.objects.filter(pk=banner.pk).update(view_count=F("view_count") + 1)


def register_click(banner: Banner) -> None:
    Banner.objects.filter(pk=banner.pk).update(click_count=F("click_count") + 1)
