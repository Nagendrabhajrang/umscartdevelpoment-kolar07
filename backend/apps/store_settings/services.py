"""Store settings business logic.

The delivery-charge calculator lives here because it is business policy, not
presentation: cart, checkout and the standalone quote endpoint all call the
same function so the numbers can never disagree.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.store_settings.models import DeliverySlab, StoreHoliday, StoreSettings
from apps.store_settings.selectors import resolve_delivery_slab
from common.exceptions import BusinessRuleError, ResourceNotFoundError
from common.utils import round_money

logger = logging.getLogger("apps.store_settings")

ZERO = Decimal("0.00")


@transaction.atomic
def update_store_settings(settings_obj: StoreSettings, **data) -> StoreSettings:
    for field_name, value in data.items():
        setattr(settings_obj, field_name, value)
    settings_obj.save()
    logger.info("Store settings updated fields=%s", sorted(data))
    return settings_obj


def calculate_delivery_charge(subtotal, settings_obj: StoreSettings | None = None) -> dict:
    """Resolve the delivery charge for a cart subtotal.

    Order of precedence:
        1. Subtotals at/above ``free_delivery_threshold`` are free.
        2. Otherwise the highest matching active :class:`DeliverySlab` applies.
        3. Otherwise the flat ``delivery_charge`` from the store settings.
    """
    settings_obj = settings_obj or StoreSettings.load()
    subtotal = round_money(subtotal or ZERO)

    if settings_obj.free_delivery_threshold and subtotal >= settings_obj.free_delivery_threshold:
        return {
            "delivery_charge": ZERO,
            "is_free_delivery": True,
            "applied_slab": None,
            "free_delivery_threshold": round_money(settings_obj.free_delivery_threshold),
            "amount_to_free_delivery": ZERO,
        }

    slab = resolve_delivery_slab(subtotal)
    if slab is not None:
        charge = round_money(slab.delivery_charge)
        applied_slab = slab.name
    else:
        charge = round_money(settings_obj.delivery_charge)
        applied_slab = None

    if charge == ZERO:
        return {
            "delivery_charge": ZERO,
            "is_free_delivery": True,
            "applied_slab": applied_slab,
            "free_delivery_threshold": round_money(settings_obj.free_delivery_threshold),
            "amount_to_free_delivery": ZERO,
        }

    amount_to_free = max(
        ZERO, round_money(settings_obj.free_delivery_threshold - subtotal)
    )
    return {
        "delivery_charge": charge,
        "is_free_delivery": False,
        "applied_slab": applied_slab,
        "free_delivery_threshold": round_money(settings_obj.free_delivery_threshold),
        "amount_to_free_delivery": amount_to_free,
    }


def assert_store_open(settings_obj: StoreSettings | None = None, check_holiday=True) -> None:
    """Raise when checkout must be blocked store-wide."""
    settings_obj = settings_obj or StoreSettings.load()
    if not settings_obj.is_store_open:
        raise BusinessRuleError(
            message=settings_obj.maintenance_message
            or "The store is currently closed. Please try again later.",
            code="store_closed",
            status_code=409,
        )
    if check_holiday:
        today = timezone.localdate()
        if StoreHoliday.objects.filter(date=today, is_active=True).exists():
            raise BusinessRuleError(
                message="The store is not accepting orders today (holiday).",
                code="store_holiday",
                status_code=409,
            )


# ---------------------------------------------------------------------------
# Delivery slabs CRUD
# ---------------------------------------------------------------------------
@transaction.atomic
def create_delivery_slab(**data) -> DeliverySlab:
    slab = DeliverySlab(**data)
    slab.full_clean(exclude=["uid", "created_at", "updated_at"])
    slab.save()
    logger.info("Delivery slab created id=%s", slab.id)
    return slab


@transaction.atomic
def update_delivery_slab(slab: DeliverySlab, **data) -> DeliverySlab:
    for field_name, value in data.items():
        setattr(slab, field_name, value)
    slab.full_clean(exclude=["uid", "created_at", "updated_at"])
    slab.save()
    return slab


@transaction.atomic
def delete_delivery_slab(slab: DeliverySlab) -> None:
    slab.delete()


def get_slab_or_404(identifier) -> DeliverySlab:
    from apps.store_settings.selectors import get_delivery_slab

    slab = get_delivery_slab(identifier)
    if slab is None:
        raise ResourceNotFoundError(
            message=f"Delivery slab '{identifier}' was not found.",
            code="delivery_slab_not_found",
        )
    return slab


# ---------------------------------------------------------------------------
# Holidays CRUD
# ---------------------------------------------------------------------------
@transaction.atomic
def create_holiday(**data) -> StoreHoliday:
    holiday = StoreHoliday(**data)
    holiday.full_clean(exclude=["uid", "created_at", "updated_at"])
    holiday.save()
    return holiday


@transaction.atomic
def update_holiday(holiday: StoreHoliday, **data) -> StoreHoliday:
    for field_name, value in data.items():
        setattr(holiday, field_name, value)
    holiday.full_clean(exclude=["uid", "created_at", "updated_at"])
    holiday.save()
    return holiday


@transaction.atomic
def delete_holiday(holiday: StoreHoliday) -> None:
    holiday.delete()


def get_holiday_or_404(identifier) -> StoreHoliday:
    from apps.store_settings.selectors import id_or_uid_q

    query = id_or_uid_q(identifier)
    holiday = StoreHoliday.objects.filter(query).first() if query else None
    if holiday is None:
        raise ResourceNotFoundError(
            message=f"Holiday '{identifier}' was not found.", code="holiday_not_found"
        )
    return holiday
