"""Order business logic: checkout, creation, status management.

**Checkout is fully transactional.** :func:`checkout` runs inside a single
``transaction.atomic()`` block that performs, in order:

1. lock the active cart (``SELECT ... FOR UPDATE``) so a double-tap on "Place
   order" cannot create two orders from one cart,
2. validate store opening hours, the cart contents, stock and minimum values,
3. lock every product's stock row in ascending id order and re-validate
   availability **while holding the locks** (oversell protection),
4. snapshot prices and addresses into the order,
5. create the order + items + status history,
6. decrement stock and write inventory movement logs,
7. redeem the coupon (locking the promotion row),
8. create the payment record (UPI pending / COD due),
9. convert the cart.

Any failure rolls the whole thing back - no half-created orders, no phantom
stock deductions.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.orders.models import (
    ACTIVE_ORDER_STATUSES,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentMethod,
    PaymentStatus,
    allowed_next_statuses,
)
from common.exceptions import (
    BusinessRuleError,
    ConflictError,
    EmptyResourceError,
    ResourceNotFoundError,
)
from common.utils import round_money

logger = logging.getLogger("apps.orders")

ZERO = Decimal("0.00")


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def get_order_or_404(identifier) -> Order:
    from apps.orders.selectors import get_order

    order = get_order(identifier)
    if order is None:
        raise ResourceNotFoundError(
            message=f"Order '{identifier}' was not found.", code="order_not_found"
        )
    return order


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------
@transaction.atomic
def checkout(*, customer, address, payment_method: str,
             customer_notes: str = "", coupon_code: str | None = None) -> Order:
    """Turn the customer's active cart into an order.

    See the module docstring for the transactional contract.
    """
    from apps.cart.models import Cart, CartStatus
    from apps.cart.services import build_cart_summary
    from apps.inventory.services import lock_stocks_for_update
    from apps.payments.services import create_payment_for_order
    from apps.promotions import services as promotion_services
    from apps.promotions.models import Promotion
    from apps.store_settings.models import StoreSettings
    from apps.store_settings.services import assert_store_open

    if payment_method not in PaymentMethod.values:
        raise BusinessRuleError(
            message=(
                "Unsupported payment method. This store accepts cash on "
                "delivery only."
            ),
            code="invalid_payment_method",
            details={"allowed": list(PaymentMethod.values)},
        )

    settings_obj = StoreSettings.load()
    assert_store_open(settings_obj)

    if payment_method == PaymentMethod.COD and not settings_obj.cod_enabled:
        raise BusinessRuleError(
            message="Cash on delivery is not available at the moment.",
            code="cod_disabled",
        )


    # 1. Lock the cart so concurrent checkouts cannot both proceed.
    # Round 25: the caller may pass an explicit cart (a guest basket that has
    # just been attached to the customer). Otherwise use the customer's own.
    cart = getattr(customer, "_checkout_cart", None)
    if cart is not None:
        cart = Cart.objects.select_for_update().filter(pk=cart.pk).first()
    else:
        cart = (
            Cart.objects.select_for_update()
            .filter(customer_id=customer.id, status=CartStatus.ACTIVE)
            .first()
        )
    if cart is None:
        # Nothing to check out is a client-side state problem, not a missing
        # resource, so 400 is the right signal for the app to send the user
        # back to the catalogue.
        raise EmptyResourceError(
            message="Your cart is empty. Add items before checking out.",
            code="empty_cart",
        )

    if coupon_code:
        cart.coupon_code = str(coupon_code).strip().upper()

    items = list(
        cart.items.select_related("product", "product__category", "product__stock")
    )
    if not items:
        raise EmptyResourceError(
            message="Your cart is empty. Add items before checking out.",
            code="empty_cart",
        )
    if len(items) > settings_obj.max_items_per_order:
        raise BusinessRuleError(
            message=(
                f"An order can contain at most {settings_obj.max_items_per_order} "
                "distinct products."
            ),
            code="too_many_items",
        )

    # 2. Validate address ownership.
    if address is None:
        raise BusinessRuleError(
            message="A delivery address is required to place an order.",
            code="address_required",
        )
    if address.customer_id != customer.id:
        raise BusinessRuleError(
            message="The delivery address does not belong to this customer.",
            code="invalid_address",
            status_code=403,
        )

    # 3. Snapshot the price breakdown before touching stock.
    summary = build_cart_summary(cart)
    subtotal = Decimal(summary["subtotal"])
    if subtotal < round_money(settings_obj.minimum_order_value):
        raise BusinessRuleError(
            message=(
                f"Minimum order value is ₹{constants_money(settings_obj.minimum_order_value)}. "
                f"Your cart total is ₹{constants_money(subtotal)}."
            ),
            code="below_minimum_order_value",
            details={
                "minimum_order_value": str(round_money(settings_obj.minimum_order_value)),
                "subtotal": str(subtotal),
            },
        )

    # 4. Lock stock rows (ascending product id) and validate availability.
    stocks = lock_stocks_for_update([item.product_id for item in items])
    unavailable = []
    for item in items:
        stock = stocks[item.product_id]
        if item.product.status != "active" or item.product.is_deleted:
            unavailable.append(
                {
                    "product_id": item.product_id,
                    "product_name": item.product.name,
                    "reason": "Product is no longer available.",
                }
            )
            continue
        if stock.track_inventory and item.quantity > stock.quantity_available:
            unavailable.append(
                {
                    "product_id": item.product_id,
                    "product_name": item.product.name,
                    "reason": "Insufficient stock.",
                    "requested": item.quantity,
                    "available": stock.quantity_available,
                }
            )
    if unavailable:
        from common.exceptions import InsufficientStockError

        raise InsufficientStockError(
            message="Some items in your cart are out of stock. Please review your cart.",
            details={"items": unavailable},
        )

    # 5. Create the order with snapshotted money and address values.
    order = Order(
        customer=customer,
        address=address,
        delivery_recipient_name=address.recipient_name,
        delivery_recipient_mobile=address.recipient_mobile,
        delivery_address_line1=address.line1,
        delivery_address_line2=address.line2,
        delivery_landmark=address.landmark,
        delivery_city=address.city,
        delivery_state=address.state,
        delivery_pincode=address.pincode,
        delivery_country=address.country,
        delivery_label=address.label,
        delivery_instructions=address.delivery_instructions,
        status=OrderStatus.PENDING,
        payment_method=payment_method,
        payment_status=PaymentStatus.COD_DUE,
        subtotal=subtotal,
        mrp_total=Decimal(summary["mrp_total"]),
        product_savings=Decimal(summary["product_savings"]),
        discount_amount=Decimal(summary["discount_amount"]),
        coupon_code=(summary["coupon_code"] or ""),
        promotion_name=(summary["applied_promotion"] or {}).get("promotion_name") or "",
        delivery_charge=Decimal(summary["delivery_charge"]),
        packaging_charge=Decimal(summary["packaging_charge"]),
        tax_amount=Decimal(summary["tax_amount"]),
        grand_total=Decimal(summary["grand_total"]),
        currency=settings_obj.currency_code,
        item_count=len(items),
        total_quantity=sum(item.quantity for item in items),
        customer_notes=customer_notes or "",
        delivery_eta_minutes=settings_obj.delivery_eta_minutes,
    )
    order.save()

    # 6. Create immutable order items.
    order_items = [
        OrderItem(
            order=order,
            product=item.product,
            product_name=item.product.name,
            product_sku=item.product.sku,
            unit_label=item.product.unit_label,
            quantity=item.quantity,
            unit_mrp=item.unit_mrp,
            unit_price=item.unit_price,
            line_total=item.line_total,
            line_savings=item.line_savings,
            tax_percent=item.product.tax_percent,
        )
        for item in items
    ]
    OrderItem.objects.bulk_create(order_items)

    # 7. Deduct stock (movement logs included).
    from apps.inventory.services import deduct_stock_for_order

    deduct_stock_for_order(order, performed_by=f"checkout:{customer.id}")

    # 8. Redeem the promotion, if one was applied.
    applied = summary.get("applied_promotion") or {}
    if applied.get("promotion_id"):
        promotion = Promotion.objects.get(pk=applied["promotion_id"])
        promotion_services.redeem_promotion(
            promotion,
            customer=customer,
            order=order,
            discount_amount=Decimal(summary["discount_amount"]),
        )

    OrderStatusHistory.objects.create(
        order=order,
        from_status="",
        to_status=OrderStatus.PENDING,
        note="Order placed",
        changed_by=f"customer:{customer.id}",
    )

    # 9. Create the payment record.
    create_payment_for_order(order)

    # 10. Convert the cart.
    from apps.cart.models import CartStatus as CS

    cart.status = CS.CONVERTED
    cart.converted_order = order
    cart.coupon_code = ""
    cart.save(update_fields=["status", "converted_order", "coupon_code", "updated_at"])
    cart.items.all().delete()

    logger.info(
        "Order created number=%s customer=%s total=%s method=%s",
        order.order_number, customer.id, order.grand_total, payment_method,
    )
    return order


def constants_money(value) -> str:
    return f"{round_money(value):.2f}"


# ---------------------------------------------------------------------------
# Status management
# ---------------------------------------------------------------------------
@transaction.atomic
def update_order_status(order: Order, new_status: str, *, note: str = "",
                        changed_by: str = "system",
                        restore_inventory: bool = True) -> Order:
    """Move an order along its lifecycle, enforcing legal transitions.

    Cancelling an order restores inventory and releases the coupon redemption.
    """
    from apps.inventory.services import restore_stock_for_order
    from apps.payments.services import mark_order_cancelled
    from apps.promotions.models import CouponRedemption
    from apps.promotions.services import release_redemption

    locked = Order.objects.select_for_update().get(pk=order.pk)

    valid_statuses = set(OrderStatus.values)
    if new_status not in valid_statuses:
        raise BusinessRuleError(
            message=f"Invalid order status '{new_status}'.",
            code="invalid_status",
            details={"allowed": sorted(valid_statuses)},
        )

    if new_status == locked.status:
        return locked

    if new_status not in allowed_next_statuses(locked.status):
        raise ConflictError(
            message=(
                f"An order in status '{locked.status}' cannot move to "
                f"'{new_status}'."
            ),
            code="invalid_status_transition",
            details={
                "current_status": locked.status,
                "requested_status": new_status,
                "allowed_next": sorted(allowed_next_statuses(locked.status)),
            },
        )

    # Cash-first rule: a delivery can only be recorded once the money is in.
    # The admin UI hides the button until the cash is recorded, but the API is
    # the real boundary - otherwise a direct call could deliver an unpaid order.
    if new_status == OrderStatus.DELIVERED and locked.payment_status not in {
        PaymentStatus.PAID, PaymentStatus.COD_COLLECTED,
    }:
        raise BusinessRuleError(
            message="Collect the cash before marking this order delivered.",
            code="payment_required_before_delivery",
            details={"payment_status": locked.payment_status},
        )

    previous = locked.status
    locked.status = new_status

    now = timezone.now()
    update_fields = ["status", "updated_at"]
    if new_status == OrderStatus.CONFIRMED:
        locked.confirmed_at = now
        update_fields.append("confirmed_at")
    elif new_status == OrderStatus.DELIVERED:
        locked.delivered_at = now
        update_fields.append("delivered_at")
        # Payment is settled separately by the payments service (the admin
        # records the cash first). Nothing is auto-collected here.
    elif new_status == OrderStatus.CANCELLED:
        locked.cancelled_at = now
        update_fields.append("cancelled_at")

    locked.save(update_fields=update_fields)

    OrderStatusHistory.objects.create(
        order=locked,
        from_status=previous,
        to_status=new_status,
        note=note or "",
        changed_by=changed_by or "system",
    )

    if new_status == OrderStatus.CANCELLED and restore_inventory:
        restore_stock_for_order(
            locked,
            reason=f"Order {locked.order_number} cancelled",
            performed_by=changed_by or "system",
        )
        redemption = CouponRedemption.objects.filter(order=locked).first()
        if redemption:
            release_redemption(redemption)
        mark_order_cancelled(locked)

    if new_status == OrderStatus.RETURNED and restore_inventory:
        restore_stock_for_order(
            locked,
            reason=f"Order {locked.order_number} returned",
            performed_by=changed_by or "system",
        )

    logger.info(
        "Order status %s -> %s order=%s by=%s",
        previous, new_status, locked.order_number, changed_by,
    )
    # Keep a caller-held instance in sync (the service re-reads under a lock).
    if order.pk == locked.pk and order is not locked:
        for field in (
            "status", "confirmed_at", "delivered_at", "cancelled_at",
            "payment_status", "updated_at",
        ):
            setattr(order, field, getattr(locked, field))
    return locked


@transaction.atomic
def cancel_order(order: Order, *, reason: str = "customer_request",
                 note: str = "", changed_by: str = "system") -> Order:
    """Customer/admin cancellation convenience wrapper."""
    from apps.orders.models import CancellationReason

    if reason not in CancellationReason.values:
        raise BusinessRuleError(
            message=f"Invalid cancellation reason '{reason}'.",
            code="invalid_cancellation_reason",
            details={"allowed": sorted(CancellationReason.values)},
        )
    # Re-read under a lock so a stale instance cannot bypass the state checks.
    locked = Order.objects.select_for_update().get(pk=order.pk)

    if locked.status == OrderStatus.CANCELLED:
        raise BusinessRuleError(
            message="This order has already been cancelled.",
            code="order_already_cancelled",
            status_code=409,
            details={"status": locked.status},
        )
    if locked.status not in {
        OrderStatus.PENDING,
        OrderStatus.CONFIRMED,
        OrderStatus.PROCESSING,
    }:
        raise BusinessRuleError(
            message=(
                "Only pending, confirmed or processing orders can be cancelled. "
                "Contact support for delivered orders."
            ),
            code="order_not_cancellable",
            status_code=409,
            details={"status": locked.status},
        )

    locked.cancellation_reason = reason
    locked.cancellation_note = note or ""
    locked.save(
        update_fields=["cancellation_reason", "cancellation_note", "updated_at"]
    )

    updated = update_order_status(
        locked,
        OrderStatus.CANCELLED,
        note=note or f"Cancelled: {dict(CancellationReason.choices).get(reason, reason)}",
        changed_by=changed_by,
    )

    # Keep the caller's instance in sync with the database.
    if updated.pk == order.pk:
        for field in (
            "status", "cancelled_at", "cancellation_reason", "cancellation_note",
            "payment_status", "updated_at",
        ):
            setattr(order, field, getattr(updated, field))
    return updated


@transaction.atomic
def confirm_order(order: Order, *, changed_by: str = "admin", note: str = "") -> Order:
    return update_order_status(order, OrderStatus.CONFIRMED, note=note, changed_by=changed_by)


@transaction.atomic
def update_internal_notes(order: Order, notes: str) -> Order:
    order.internal_notes = notes or ""
    order.save(update_fields=["internal_notes", "updated_at"])
    return order


@transaction.atomic
def mark_delivered(order: Order, *, changed_by: str = "admin", note: str = "") -> Order:
    return update_order_status(order, OrderStatus.DELIVERED, note=note, changed_by=changed_by)


def get_customer_order_or_404(customer, identifier) -> Order:
    order = get_order_or_404(identifier)
    if order.customer_id != customer.id:
        raise ResourceNotFoundError(
            message=f"Order '{identifier}' was not found for this customer.",
            code="order_not_found",
        )
    return order


def assert_order_is_active(order: Order) -> None:
    if order.status not in ACTIVE_ORDER_STATUSES:
        raise BusinessRuleError(
            message=f"This action is not allowed for an order that is '{order.status}'.",
            code="order_not_active",
            status_code=409,
        )


@transaction.atomic
def reorder(customer, order: Order) -> dict:
    """Add every still-available item of a past order back into the cart."""
    from apps.cart.services import add_to_cart
    from apps.catalog.models import Product

    if order.customer_id != customer.id:
        raise BusinessRuleError(
            message="This order belongs to another customer.",
            code="order_forbidden",
            status_code=403,
        )

    added, skipped = [], []
    for item in order.items.select_related("product"):
        product = Product.objects.filter(pk=item.product_id, is_deleted=False).first()
        if product is None or product.status != Product.Status.ACTIVE:
            skipped.append({"product": item.product_name, "reason": "no longer available"})
            continue
        try:
            add_to_cart(customer, product, quantity=item.quantity)
            added.append({"product": product.name, "quantity": item.quantity})
        except BusinessRuleError as exc:
            skipped.append({"product": product.name, "reason": str(exc.detail)})
    logger.info("Reorder order=%s added=%s skipped=%s",
                order.order_number, len(added), len(skipped))
    return {"added": added, "skipped": skipped}
