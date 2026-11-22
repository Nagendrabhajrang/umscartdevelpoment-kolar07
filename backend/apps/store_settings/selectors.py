"""Read-only queries for store settings."""

from decimal import Decimal

from django.db.models import QuerySet
from django.utils import timezone

from apps.store_settings.models import DeliverySlab, StoreHoliday, StoreSettings
from common.selectors import id_or_uid_q


def get_store_settings() -> StoreSettings:
    return StoreSettings.load()


def list_delivery_slabs(active_only: bool = False) -> QuerySet[DeliverySlab]:
    queryset = DeliverySlab.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)
    return queryset.order_by("min_order_value")


def get_delivery_slab(identifier) -> DeliverySlab | None:
    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return DeliverySlab.objects.filter(query).first()


def resolve_delivery_slab(subtotal) -> DeliverySlab | None:
    """Highest matching active slab for ``subtotal``."""
    subtotal = Decimal(str(subtotal or 0))
    candidates = [
        slab
        for slab in DeliverySlab.objects.filter(is_active=True).order_by("-min_order_value")
        if slab.applies_to(subtotal)
    ]
    return candidates[0] if candidates else None


def list_holidays(upcoming_only: bool = False) -> QuerySet[StoreHoliday]:
    queryset = StoreHoliday.objects.all()
    if upcoming_only:
        queryset = queryset.filter(date__gte=timezone.localdate())
    return queryset


def is_holiday(date=None) -> bool:
    date = date or timezone.localdate()
    return StoreHoliday.objects.filter(date=date, is_active=True).exists()
