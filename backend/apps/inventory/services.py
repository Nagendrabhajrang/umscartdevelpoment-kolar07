"""Inventory business logic.

**Concurrency contract** - every function that changes stock runs inside an
atomic block and takes a ``SELECT ... FOR UPDATE`` lock on the ``Stock`` row
before reading the current quantity. Checkout paths lock *all* involved stock
rows in ascending product-id order (see
:func:`lock_stocks_for_update`) which eliminates deadlocks between two
concurrent orders touching the same products in different sequence.
"""

import logging
from collections import OrderedDict

from django.db import transaction
from django.db.models import F

from apps.inventory.models import InventoryLog, Stock, StockMovementType
from common.exceptions import (
    BusinessRuleError,
    InsufficientStockError,
    ResourceNotFoundError,
)

logger = logging.getLogger("apps.inventory")


# ---------------------------------------------------------------------------
# Locking helpers
# ---------------------------------------------------------------------------
def lock_stock(product_id: int) -> Stock:
    """Lock and return the stock row for ``product_id``.

    MUST be called inside a transaction; ``select_for_update`` is a no-op
    otherwise. Raises ``ResourceNotFoundError`` if the product has no stock row.
    """
    stock = (
        Stock.objects.select_for_update()
        .select_related("product")
        .filter(product_id=product_id)
        .first()
    )
    if stock is None:
        raise ResourceNotFoundError(
            message=f"No inventory record exists for product {product_id}.",
            code="stock_record_missing",
            details={"product": product_id},
        )
    return stock


def lock_stocks_for_update(product_ids) -> "OrderedDict[int, Stock]":
    """Lock several stock rows in a deterministic order to avoid deadlocks."""
    ordered_ids = sorted({int(pid) for pid in product_ids})
    stocks = (
        Stock.objects.select_for_update()
        .select_related("product")
        .filter(product_id__in=ordered_ids)
        .order_by("product_id")
    )
    result = OrderedDict((stock.product_id, stock) for stock in stocks)
    missing = [pid for pid in ordered_ids if pid not in result]
    if missing:
        raise ResourceNotFoundError(
            message="Stock records are missing for one or more products.",
            code="stock_record_missing",
            details={"product_ids": missing},
        )
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _sync_product_cache(stock: Stock, product=None) -> None:
    """Refresh the in-memory ``product.stock`` reverse cache after a mutation.

    ``product.stock`` is a *cached* reverse one-to-one descriptor. The service
    loads its own ``Product`` instance through ``select_related``, so the
    caller's instance must be refreshed explicitly - otherwise a caller that
    read ``product.stock`` before the call keeps seeing the stale quantity for
    the lifetime of that object.
    """
    from apps.catalog.models import Product

    targets = []
    if isinstance(product, Product):
        targets.append(product)
    service_product = getattr(stock, "product", None)
    if isinstance(service_product, Product):
        targets.append(service_product)

    for target in targets:
        cache = getattr(target._state, "fields_cache", None)
        if cache is not None:
            cache["stock"] = stock


def _log_movement(stock: Stock, movement_type: str, quantity_change: int,
                  quantity_before: int, quantity_after: int, reference: str = "",
                  reason: str = "", performed_by: str = "") -> InventoryLog:
    return InventoryLog.objects.create(
        stock=stock,
        product=stock.product,
        movement_type=movement_type,
        quantity_change=quantity_change,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        reference=reference or "",
        reason=reason or "",
        performed_by=performed_by or "",
    )


def _apply_available_check(stock: Stock, requested: int, product_name: str) -> None:
    available = stock.quantity_available
    if requested > available:
        raise InsufficientStockError(
            message=(
                f"Only {available} unit(s) of '{product_name}' are available, "
                f"but {requested} were requested."
            ),
            details={
                "product_id": stock.product_id,
                "product_name": product_name,
                "requested": requested,
                "available": available,
            },
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@transaction.atomic
def set_initial_stock(product, quantity: int = 0, low_stock_threshold: int | None = None,
                      performed_by: str = "") -> Stock:
    """Create (or reset) the stock row for a newly created product."""
    if quantity < 0:
        raise BusinessRuleError(
            message="Initial quantity cannot be negative.", code="invalid_quantity"
        )
    stock, created = Stock.objects.select_for_update().get_or_create(
        product=product,
        defaults={
            "quantity": quantity,
            "low_stock_threshold": low_stock_threshold if low_stock_threshold is not None else 5,
        },
    )
    if not created and quantity:
        before = stock.quantity
        stock.quantity += quantity
        stock.save(update_fields=["quantity", "updated_at"])
        _log_movement(
            stock, StockMovementType.ADJUSTMENT, quantity, before, stock.quantity,
            reason="Additional initial stock", performed_by=performed_by,
        )
    elif created and quantity:
        _log_movement(
            stock, StockMovementType.INITIAL, quantity, 0, quantity,
            reason="Initial stock", performed_by=performed_by,
        )
    _sync_product_cache(stock, product)
    return stock


@transaction.atomic
def add_stock(product, quantity: int, *, movement_type: str = StockMovementType.PURCHASE,
              reference: str = "", reason: str = "", performed_by: str = "") -> Stock:
    """Increase stock (goods received, returns, positive adjustments)."""
    if quantity <= 0:
        raise BusinessRuleError(
            message="Quantity to add must be greater than zero.",
            code="invalid_quantity",
            details={"quantity": quantity},
        )
    product_id = getattr(product, "id", product)
    stock = lock_stock(product_id)
    before = stock.quantity
    stock.quantity = F("quantity") + quantity
    stock.save(update_fields=["quantity", "updated_at"])
    stock.refresh_from_db(fields=["quantity"])
    _log_movement(
        stock, movement_type, quantity, before, stock.quantity, reference, reason,
        performed_by,
    )
    logger.info(
        "Stock added product=%s qty=%s new=%s type=%s",
        product_id, quantity, stock.quantity, movement_type,
    )
    _sync_product_cache(stock, product)
    return stock


@transaction.atomic
def remove_stock(product, quantity: int, *,
                 movement_type: str = StockMovementType.ADJUSTMENT,
                 reference: str = "", reason: str = "",
                 performed_by: str = "") -> Stock:
    """Decrease stock (damage, wastage, negative adjustment). Never goes below 0."""
    if quantity <= 0:
        raise BusinessRuleError(
            message="Quantity to remove must be greater than zero.",
            code="invalid_quantity",
        )
    product_id = getattr(product, "id", product)
    stock = lock_stock(product_id)
    if quantity > stock.quantity:
        raise InsufficientStockError(
            message=(
                f"Cannot remove {quantity} unit(s); only {stock.quantity} are on hand."
            ),
            details={
                "product_id": product_id,
                "requested": quantity,
                "on_hand": stock.quantity,
            },
        )
    before = stock.quantity
    stock.quantity -= quantity
    stock.save(update_fields=["quantity", "updated_at"])
    _log_movement(
        stock, movement_type, -quantity, before, stock.quantity, reference, reason,
        performed_by,
    )
    logger.info("Stock removed product=%s qty=%s new=%s", product_id, quantity, stock.quantity)
    _sync_product_cache(stock, product)
    return stock


@transaction.atomic
def adjust_stock(product, new_quantity: int, *, reason: str = "",
                 performed_by: str = "") -> Stock:
    """Set the on-hand quantity to an absolute value (stock count)."""
    if new_quantity < 0:
        raise BusinessRuleError(
            message="Quantity cannot be negative.", code="invalid_quantity"
        )
    product_id = getattr(product, "id", product)
    stock = lock_stock(product_id)
    before = stock.quantity
    delta = new_quantity - before
    if delta == 0:
        return stock
    stock.quantity = new_quantity
    stock.save(update_fields=["quantity", "updated_at"])
    _log_movement(
        stock, StockMovementType.ADJUSTMENT, delta, before, stock.quantity,
        reason=reason or "Manual stock adjustment", performed_by=performed_by,
    )
    logger.info("Stock adjusted product=%s %s -> %s", product_id, before, new_quantity)
    _sync_product_cache(stock, product)
    return stock


@transaction.atomic
def set_low_stock_threshold(product, threshold: int) -> Stock:
    if threshold < 0:
        raise BusinessRuleError(
            message="Threshold cannot be negative.", code="invalid_quantity"
        )
    product_id = getattr(product, "id", product)
    stock = lock_stock(product_id)
    stock.low_stock_threshold = threshold
    stock.save(update_fields=["low_stock_threshold", "updated_at"])
    return stock


def check_availability(product, quantity: int) -> bool:
    """Non-locking availability probe used for cart validation."""
    stock = Stock.objects.filter(product_id=getattr(product, "id", product)).first()
    if stock is None:
        return False
    if not stock.track_inventory:
        return True
    return stock.quantity_available >= quantity


@transaction.atomic
def reserve_stock(product, quantity: int, *, reference: str = "",
                  performed_by: str = "") -> Stock:
    """Soft-reserve units without removing them from on-hand quantity."""
    if quantity <= 0:
        raise BusinessRuleError(message="Quantity must be positive.", code="invalid_quantity")
    stock = lock_stock(getattr(product, "id", product))
    _apply_available_check(stock, quantity, stock.product.name)
    stock.reserved_quantity += quantity
    stock.save(update_fields=["reserved_quantity", "updated_at"])
    _log_movement(
        stock, StockMovementType.RESERVATION, 0, stock.quantity, stock.quantity,
        reference=reference, reason=f"Reserved {quantity} unit(s)", performed_by=performed_by,
    )
    return stock


@transaction.atomic
def release_reservation(product, quantity: int, *, reference: str = "",
                        performed_by: str = "") -> Stock:
    stock = lock_stock(getattr(product, "id", product))
    stock.reserved_quantity = max(0, stock.reserved_quantity - quantity)
    stock.save(update_fields=["reserved_quantity", "updated_at"])
    _log_movement(
        stock, StockMovementType.RELEASE, 0, stock.quantity, stock.quantity,
        reference=reference, reason=f"Released {quantity} unit(s)", performed_by=performed_by,
    )
    return stock


@transaction.atomic
def deduct_stock_for_order(order, performed_by: str = "system") -> list[InventoryLog]:
    """Deduct the stock for every item of ``order``.

    Called from the checkout service inside the same transaction as the order
    creation. Locks every involved stock row in ascending product-id order and
    re-validates availability while holding the locks, so two concurrent
    checkouts cannot oversell.
    """
    items = list(order.items.select_related("product").all())
    if not items:
        raise BusinessRuleError(
            message="An order with no items cannot consume stock.",
            code="empty_order",
        )

    stocks = lock_stocks_for_update([item.product_id for item in items])
    logs = []

    # Validate everything first so a failure leaves no partial deductions.
    for item in items:
        stock = stocks[item.product_id]
        if not stock.track_inventory:
            continue
        _apply_available_check(stock, item.quantity, item.product_name)

    for item in items:
        stock = stocks[item.product_id]
        if not stock.track_inventory:
            continue
        before = stock.quantity
        stock.quantity -= item.quantity
        stock.save(update_fields=["quantity", "updated_at"])
        logs.append(
            _log_movement(
                stock,
                StockMovementType.SALE,
                -item.quantity,
                before,
                stock.quantity,
                reference=order.order_number,
                reason=f"Order {order.order_number}",
                performed_by=performed_by,
            )
        )

    for stock in stocks.values():
        _sync_product_cache(stock)

    logger.info(
        "Stock deducted for order=%s items=%s", order.order_number, len(items)
    )
    return logs


@transaction.atomic
def restore_stock_for_order(order, *, movement_type: str = StockMovementType.RETURN,
                            reason: str = "", performed_by: str = "system") -> list[InventoryLog]:
    """Return the stock of every item of ``order`` (cancellation / return)."""
    items = list(order.items.select_related("product").all())
    if not items:
        return []

    stocks = lock_stocks_for_update([item.product_id for item in items])
    logs = []
    for item in items:
        stock = stocks[item.product_id]
        before = stock.quantity
        stock.quantity += item.quantity
        stock.save(update_fields=["quantity", "updated_at"])
        logs.append(
            _log_movement(
                stock,
                movement_type,
                item.quantity,
                before,
                stock.quantity,
                reference=order.order_number,
                reason=reason or f"Stock restored for order {order.order_number}",
                performed_by=performed_by,
            )
        )
    for stock in stocks.values():
        _sync_product_cache(stock)

    logger.info("Stock restored for order=%s items=%s", order.order_number, len(items))
    return logs


def get_stock_or_404(identifier) -> Stock:
    from apps.inventory.selectors import get_stock_or_uid

    stock = get_stock_or_uid(identifier)
    if stock is None:
        raise ResourceNotFoundError(
            message=f"Stock record '{identifier}' was not found.", code="stock_not_found"
        )
    return stock


@transaction.atomic
def toggle_tracking(stock: Stock, track: bool) -> Stock:
    stock.track_inventory = track
    stock.save(update_fields=["track_inventory", "updated_at"])
    return stock


def reconcile_stock_report() -> list[dict]:
    """Products whose cached stock disagrees with the movement log.

    Useful as a nightly integrity job. Compares ``stock.quantity`` with the sum
    of all movement deltas for that product.
    """
    from django.db.models import Sum

    discrepancies = []
    totals = (
        InventoryLog.objects.values("product_id")
        .annotate(delta=Sum("quantity_change"))
        .order_by("product_id")
    )
    delta_by_product = {row["product_id"]: row["delta"] or 0 for row in totals}
    for stock in Stock.objects.select_related("product").iterator(chunk_size=500):
        expected = delta_by_product.get(stock.product_id, 0)
        if expected != stock.quantity:
            discrepancies.append(
                {
                    "product_id": stock.product_id,
                    "product_name": stock.product.name,
                    "recorded_quantity": stock.quantity,
                    "movement_total": expected,
                    "difference": stock.quantity - expected,
                }
            )
    return discrepancies
