"""Cart business logic.

All mutations go through this module. Invariants enforced here:

* a customer has exactly one active cart (auto-created on demand),
* a product appears at most once per cart (quantity is incremented instead),
* quantities respect stock availability and the product's
  ``max_order_quantity``,
* only products that are ``active`` and not soft-deleted can be added,
* price/MRP snapshots are taken at add time; totals are always derived.

Coupon application is delegated to the promotions app so pricing rules live in
one place.
"""

import logging
from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.cart.models import Cart, CartItem, CartStatus
from common.exceptions import (
    BusinessRuleError,
    ResourceNotFoundError,
)

logger = logging.getLogger("apps.cart")

MAX_ITEM_QUANTITY = 999


# ---------------------------------------------------------------------------
# Cart lifecycle
# ---------------------------------------------------------------------------
def get_or_create_active_cart(customer) -> Cart:
    """Return the customer's active cart, creating one atomically if needed.

    The common case is a plain read. Creation runs in its own atomic block so a
    lost race (two tabs opening the storefront at once) only rolls back the
    ``INSERT``; the handler can then re-read the winner's row. Catching
    ``IntegrityError`` around the insert *inside* one transaction would leave
    that transaction aborted and the follow-up SELECT would itself raise
    ``TransactionManagementError``.
    """
    customer_id = getattr(customer, "id", customer)
    cart = (
        Cart.objects.filter(customer_id=customer_id, status=CartStatus.ACTIVE)
        .order_by("-id")
        .first()
    )
    if cart is not None:
        return cart

    try:
        with transaction.atomic():
            cart = Cart.objects.create(customer_id=customer_id, status=CartStatus.ACTIVE)
        logger.info("Cart created id=%s customer=%s", cart.id, customer_id)
        return cart
    except IntegrityError:
        # Another request won the race; its cart is the one to use.
        return (
            Cart.objects.filter(customer_id=customer_id, status=CartStatus.ACTIVE)
            .order_by("-id")
            .get()
        )


@transaction.atomic
def clear_cart(cart: Cart) -> Cart:
    cart.items.all().delete()
    cart.coupon_code = ""
    cart.save(update_fields=["coupon_code", "updated_at"])
    logger.info("Cart cleared id=%s", cart.id)
    return cart


@transaction.atomic
def abandon_cart(cart: Cart) -> Cart:
    if cart.status == CartStatus.CONVERTED:
        raise BusinessRuleError(
            message="A converted cart cannot be abandoned.",
            code="cart_already_converted",
        )
    cart.status = CartStatus.ABANDONED
    cart.save(update_fields=["status", "updated_at"])
    return cart


# ---------------------------------------------------------------------------
# Item operations
# ---------------------------------------------------------------------------
def _validate_product_sellable(product) -> None:
    """The product exists, is published and has not been removed."""
    from apps.catalog.models import Product

    if product.is_deleted:
        raise ResourceNotFoundError(
            message="This product is no longer available.",
            code="product_unavailable",
            details={"product_id": product.id},
        )
    if product.status != Product.Status.ACTIVE:
        raise BusinessRuleError(
            message=f"'{product.name}' is not currently available for purchase.",
            code="product_not_purchasable",
            details={"product_id": product.id, "status": product.status},
        )


def _validate_quantity_cap(product, quantity: int) -> None:
    """The per-order quantity cap configured on the product."""
    if quantity > product.max_order_quantity:
        raise BusinessRuleError(
            message=(
                f"You can order at most {product.max_order_quantity} unit(s) of "
                f"'{product.name}' in a single order."
            ),
            code="max_order_quantity_exceeded",
            details={
                "product_id": product.id,
                "max_order_quantity": product.max_order_quantity,
                "requested": quantity,
            },
        )


def _validate_product_purchasable(product, quantity: int) -> None:
    """Full validation: sellable -> in stock -> within the per-order cap.

    Stock is checked before the quantity cap so the customer gets the more
    actionable message ("only 3 left") instead of a policy limit.
    """
    _validate_product_sellable(product)
    _validate_stock(product, quantity)
    _validate_quantity_cap(product, quantity)


def _validate_stock(product, quantity: int) -> None:
    from apps.inventory.models import Stock

    stock = Stock.objects.filter(product_id=product.id).first()
    if stock is None or not stock.track_inventory:
        return
    if quantity > stock.quantity_available:
        # InsufficientStockError -> HTTP 409 with code "insufficient_stock";
        # it is the canonical "not enough units" signal across the code base.
        from common.exceptions import InsufficientStockError

        raise InsufficientStockError(
            message=(
                f"Only {stock.quantity_available} unit(s) of '{product.name}' are "
                f"currently in stock."
            ),
            code="insufficient_stock",
            details={
                "product_id": product.id,
                "requested": quantity,
                "available": stock.quantity_available,
            },
        )


@transaction.atomic
def add_to_cart(customer, product, quantity: int = 1, notes: str = "") -> CartItem:
    """Add ``quantity`` units of ``product`` to the customer's active cart."""
    if quantity < 1:
        raise BusinessRuleError(
            message="Quantity must be at least 1.", code="invalid_quantity"
        )

    cart = get_or_create_active_cart(customer)
    _validate_product_purchasable(product, quantity)

    existing = (
        CartItem.objects.select_for_update()
        .filter(cart=cart, product=product)
        .first()
    )
    target_quantity = (existing.quantity if existing else 0) + quantity
    _validate_product_purchasable(product, target_quantity)
    _validate_stock(product, target_quantity)

    if existing:
        existing.quantity = target_quantity
        if notes:
            existing.notes = notes
        # Adopt the latest price when the customer re-adds the same product.
        existing.refresh_price(save=False)
        existing.save(
            update_fields=[
                "quantity", "unit_price", "unit_mrp", "product_name_snapshot",
                "notes", "updated_at",
            ]
        )
        cart.save(update_fields=["updated_at"])
        logger.info(
            "Cart item quantity updated cart=%s product=%s qty=%s",
            cart.id, product.id, target_quantity,
        )
        return existing

    item = CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=quantity,
        unit_price=product.selling_price,
        unit_mrp=product.mrp,
        product_name_snapshot=product.name,
        notes=notes or "",
    )
    cart.save(update_fields=["updated_at"])
    _invalidate_coupon_if_needed(cart)
    logger.info("Cart item added cart=%s product=%s qty=%s", cart.id, product.id, quantity)
    return item


@transaction.atomic
def add_item_to_cart(cart: Cart, product, quantity: int = 1, notes: str = "") -> CartItem:
    """Add a product to a *specific* cart (guest baskets have no Customer).

    Same validation and price snapshotting as :func:`add_to_cart`; only the
    cart lookup differs, so a guest line and an account line behave identically
    and merge cleanly on login.
    """
    if quantity < 1:
        raise BusinessRuleError(
            message="Quantity must be at least 1.", code="invalid_quantity"
        )
    _validate_product_purchasable(product, quantity)

    existing = (
        CartItem.objects.select_for_update().filter(cart=cart, product=product).first()
    )
    target_quantity = (existing.quantity if existing else 0) + quantity
    _validate_product_purchasable(product, target_quantity)
    _validate_stock(product, target_quantity)

    if existing:
        existing.quantity = target_quantity
        if notes:
            existing.notes = notes
        existing.refresh_price(save=False)
        existing.save(
            update_fields=[
                "quantity", "unit_price", "unit_mrp", "product_name_snapshot",
                "notes", "updated_at",
            ]
        )
        cart.save(update_fields=["updated_at"])
        return existing

    item = CartItem.objects.create(
        cart=cart,
        product=product,
        quantity=quantity,
        unit_price=product.selling_price,
        unit_mrp=product.mrp,
        product_name_snapshot=product.name,
        notes=notes or "",
    )
    cart.save(update_fields=["updated_at"])
    _invalidate_coupon_if_needed(cart)
    logger.info("Cart item added (cart-level) cart=%s product=%s qty=%s", cart.id, product.id, quantity)
    return item


@transaction.atomic
def update_cart_item(item: CartItem, quantity: int, notes: str | None = None) -> CartItem:
    """Set an absolute quantity for a cart line (``0`` removes the line)."""
    if quantity < 0:
        raise BusinessRuleError(
            message="Quantity cannot be negative.", code="invalid_quantity"
        )
    if quantity == 0:
        cart = item.cart
        item.delete()
        cart.save(update_fields=["updated_at"])
        _invalidate_coupon_if_needed(cart)
        logger.info("Cart item removed via zero quantity cart=%s", cart.id)
        return None

    if not item.cart.is_active:
        raise BusinessRuleError(
            message="This cart is no longer active.", code="cart_not_active"
        )

    _validate_product_purchasable(item.product, quantity)
    _validate_stock(item.product, quantity)

    item.quantity = min(quantity, MAX_ITEM_QUANTITY)
    if notes is not None:
        item.notes = notes
    item.save(update_fields=["quantity", "notes", "updated_at"])
    item.cart.save(update_fields=["updated_at"])
    _invalidate_coupon_if_needed(item.cart)
    logger.info("Cart item updated id=%s qty=%s", item.id, item.quantity)
    return item


@transaction.atomic
def increment_cart_item(item: CartItem, delta: int = 1) -> CartItem:
    return update_cart_item(item, item.quantity + delta, item.notes)


@transaction.atomic
def remove_cart_item(item: CartItem) -> None:
    cart = item.cart
    item_id = item.id
    item.delete()
    cart.save(update_fields=["updated_at"])
    _invalidate_coupon_if_needed(cart)
    logger.info("Cart item removed id=%s cart=%s", item_id, cart.id)


@transaction.atomic
def refresh_cart_prices(cart: Cart) -> Cart:
    """Adopt the latest product prices for every line in the cart."""
    for item in cart.items.select_related("product").all():
        item.refresh_price()
    cart.save(update_fields=["updated_at"])
    return cart


# ---------------------------------------------------------------------------
# Guest baskets (round 23)
# ---------------------------------------------------------------------------
# The storefront lets a shopper fill a cart before signing in. The browser
# generates a key and keeps it in localStorage; the basket lives on the server
# so the totals, the stock checks and the coupon rules are the same as they are
# for a signed-in customer. On login the guest cart is merged into the account's
# own cart and marked ``merged``, so it can never be replayed twice.
MIN_GUEST_KEY_LENGTH = 8
MAX_GUEST_KEY_LENGTH = 64


def normalise_guest_key(raw) -> str:
    """Validate a browser-supplied basket key.

    Anything shorter than 8 characters is rejected: a guessable key would let
    one visitor read another's basket, and an 8-character floor plus a random
    UUID in the browser makes that impractical. This is still a convenience
    seam, not an authentication boundary - a guest basket holds no personal
    data and can never become an order on its own.
    """
    key = str(raw or "").strip()
    if not key:
        return ""
    if len(key) < MIN_GUEST_KEY_LENGTH:
        raise BusinessRuleError(
            message="The guest cart key is too short.", code="invalid_guest_key"
        )
    if len(key) > MAX_GUEST_KEY_LENGTH:
        raise BusinessRuleError(
            message="The guest cart key is too long.", code="invalid_guest_key"
        )
    if not all(ch.isalnum() or ch in "-_" for ch in key):
        raise BusinessRuleError(
            message="The guest cart key contains invalid characters.",
            code="invalid_guest_key",
        )
    return key


def get_guest_cart(guest_key: str, create: bool = False) -> Cart | None:
    """Return the live basket for ``guest_key`` (optionally creating it)."""
    key = normalise_guest_key(guest_key)
    if not key:
        return None
    cart = (
        Cart.objects.filter(guest_key=key, status=CartStatus.ACTIVE, customer__isnull=True)
        .order_by("-id")
        .first()
    )
    if cart is not None or not create:
        return cart
    try:
        with transaction.atomic():
            cart = Cart.objects.create(guest_key=key, status=CartStatus.ACTIVE)
        logger.info("Guest cart created key=%s id=%s", key, cart.id)
        return cart
    except IntegrityError:  # pragma: no cover - no unique index on guest_key
        return (
            Cart.objects.filter(guest_key=key, status=CartStatus.ACTIVE)
            .order_by("-id")
            .first()
        )


def guest_cart_has_items(guest_key: str) -> bool:
    """True when this browser has a live guest basket with at least one line.

    Round 32: used while signing in to tell the client whether a basket is still
    waiting to be folded into the new account. It only *reads* - the merge
    itself is deferred until a request proves the session cookie works.
    """
    cart = get_guest_cart(guest_key, create=False)
    if cart is None:
        return False
    return cart.items.exists()


def adopt_guest_cart(guest_key: str, customer) -> int:
    """Fold a guest basket into ``customer``'s cart, idempotently.

    Returns the number of lines moved (0 when there was nothing to move).
    Safe to call on every authenticated cart request: a key whose basket has
    already been merged has no live guest cart left, so it is a cheap no-op.
    """
    key = normalise_guest_key(guest_key)
    if not key:
        return 0
    # Never let a basket problem break the request that triggered it: the caller
    # is a plain cart read, and the shopper should still see their account cart
    # even if the stale guest basket cannot be folded in.
    try:
        if get_guest_cart(key, create=False) is None:
            return 0
        _, moved = merge_guest_cart_into(key, customer)
    except Exception:  # pragma: no cover - defensive
        logger.exception("Deferred guest cart merge failed key=%s customer=%s", key, customer.pk)
        return 0
    if moved:
        logger.info("Deferred guest cart merge key=%s customer=%s lines=%s", key, customer.pk, moved)
    return moved


@transaction.atomic
def merge_guest_cart_into(guest_key: str, customer) -> tuple[Cart, int]:
    """Fold a guest basket into ``customer``'s active cart.

    Returns ``(cart, moved_line_count)``. Everything lives in one transaction:
    a failure must not leave the guest basket half-moved.
    """
    key = normalise_guest_key(guest_key)
    target = get_or_create_active_cart(customer)
    if not key:
        return target, 0

    source = (
        Cart.objects.select_for_update()
        .filter(guest_key=key, status=CartStatus.ACTIVE, customer__isnull=True)
        .order_by("-id")
        .first()
    )
    if source is None or source.pk == target.pk:
        return target, 0

    moved = 0
    for item in source.items.select_related("product"):
        existing = (
            CartItem.objects.select_for_update()
            .filter(cart=target, product=item.product)
            .first()
        )
        if existing:
            existing.quantity = min(existing.quantity + item.quantity, MAX_ITEM_QUANTITY)
            existing.save(update_fields=["quantity", "updated_at"])
        else:
            item.cart = target
            item.save(update_fields=["cart", "updated_at"])
        moved += 1

    source.status = CartStatus.MERGED
    source.coupon_code = ""
    source.save(update_fields=["status", "coupon_code", "updated_at"])
    target.save(update_fields=["updated_at"])
    logger.info(
        "Guest cart merged guest_key=%s source=%s target=%s lines=%s",
        key, source.id, target.id, moved,
    )
    return target, moved


@transaction.atomic
def merge_carts(source_cart: Cart, target_cart: Cart) -> Cart:
    """Merge a guest/old cart into the target cart (used post-login)."""
    if source_cart.pk == target_cart.pk:
        return target_cart
    if not target_cart.is_active:
        raise BusinessRuleError(
            message="The target cart is not active.", code="cart_not_active"
        )

    for item in source_cart.items.select_related("product"):
        existing = CartItem.objects.filter(
            cart=target_cart, product=item.product
        ).first()
        if existing:
            existing.quantity = min(
                existing.quantity + item.quantity, MAX_ITEM_QUANTITY
            )
            existing.save(update_fields=["quantity", "updated_at"])
        else:
            item.cart = target_cart
            item.save(update_fields=["cart", "updated_at"])
    source_cart.status = CartStatus.MERGED
    source_cart.save(update_fields=["status", "updated_at"])
    logger.info("Cart merged source=%s target=%s", source_cart.id, target_cart.id)
    return target_cart


# ---------------------------------------------------------------------------
# Coupons
# ---------------------------------------------------------------------------
@transaction.atomic
def apply_coupon(cart: Cart, code: str) -> dict:
    """Validate and store a coupon on the cart. Returns the evaluation result."""
    from apps.promotions import services as promotion_services

    items = list(cart.items.select_related("product", "product__category"))
    if not items:
        raise BusinessRuleError(
            message="Add items to your cart before applying a coupon.",
            code="empty_cart",
        )

    result = promotion_services.evaluate_coupon(
        code, cart.customer, items, cart.subtotal
    )
    if not result.applied:
        raise BusinessRuleError(
            message=result.message or "This coupon cannot be applied.",
            code="coupon_not_applicable",
            details={"code": code},
        )

    cart.coupon_code = str(code).strip().upper()
    cart.save(update_fields=["coupon_code", "updated_at"])
    logger.info("Coupon applied cart=%s code=%s", cart.id, cart.coupon_code)
    return result.as_dict()


@transaction.atomic
def remove_coupon(cart: Cart) -> Cart:
    cart.coupon_code = ""
    cart.save(update_fields=["coupon_code", "updated_at"])
    return cart


def _invalidate_coupon_if_needed(cart: Cart) -> None:
    """Drop a stored coupon when the cart no longer qualifies for it."""
    if not cart.coupon_code:
        return
    from apps.promotions import services as promotion_services

    items = list(cart.items.select_related("product", "product__category"))
    if not items:
        cart.coupon_code = ""
        cart.save(update_fields=["coupon_code", "updated_at"])
        return
    result = promotion_services.evaluate_coupon(
        cart.coupon_code, cart.customer, items, cart.subtotal
    )
    if not result.applied:
        cart.coupon_code = ""
        cart.save(update_fields=["coupon_code", "updated_at"])
        logger.info("Coupon invalidated for cart=%s", cart.id)


# ---------------------------------------------------------------------------
# Pricing summary (consumed by the cart detail endpoint and checkout)
# ---------------------------------------------------------------------------
def build_cart_summary(cart: Cart, delivery_address=None) -> dict:
    """Compute the full price breakdown for a cart.

    This is the single source of truth for cart totals: subtotal, savings,
    coupon discount, delivery charge and grand total.
    """
    from apps.promotions import services as promotion_services
    from apps.store_settings.models import StoreSettings
    from apps.store_settings.services import calculate_delivery_charge
    from common.utils import round_money

    settings_obj = StoreSettings.load()
    items = list(cart.items.select_related("product", "product__category"))
    subtotal = round_money(sum((item.line_total for item in items), Decimal("0.00")))
    mrp_total = round_money(sum((item.line_mrp_total for item in items), Decimal("0.00")))

    # 1. Automatic (code-less) promotions
    auto = promotion_services.find_best_automatic_promotion(
        cart.customer, items, subtotal
    )

    # 2. Stored coupon - it wins when it beats the automatic offer.
    coupon_result = None
    if cart.coupon_code:
        coupon_result = promotion_services.evaluate_coupon(
            cart.coupon_code, cart.customer, items, subtotal
        )
        if not coupon_result.applied:
            coupon_result = None

    if coupon_result and coupon_result.discount_amount >= auto.discount_amount:
        best = coupon_result
    elif auto.applied:
        best = auto
    else:
        best = None

    discount_amount = round_money(best.discount_amount) if best else Decimal("0.00")
    free_delivery = bool(best and best.free_delivery)

    discounted_subtotal = max(Decimal("0.00"), subtotal - discount_amount)

    if free_delivery:
        delivery = {
            "delivery_charge": Decimal("0.00"),
            "is_free_delivery": True,
            "applied_slab": "Promotion: free delivery",
            "free_delivery_threshold": round_money(settings_obj.free_delivery_threshold),
            "amount_to_free_delivery": Decimal("0.00"),
        }
    else:
        delivery = calculate_delivery_charge(discounted_subtotal, settings_obj)

    packaging = round_money(settings_obj.packaging_charge)
    delivery_charge = round_money(delivery["delivery_charge"])

    tax_base = discounted_subtotal
    if settings_obj.apply_tax_on_delivery:
        tax_base += delivery_charge
    tax_amount = round_money(
        tax_base * round_money(settings_obj.default_tax_percent) / Decimal("100")
    )

    grand_total = round_money(
        discounted_subtotal + delivery_charge + packaging + tax_amount
    )

    issues = _collect_issues(cart, items, subtotal, settings_obj)

    return {
        "cart_id": cart.id,
        "cart_uid": str(cart.uid),
        "status": cart.status,
        "item_count": len(items),
        "total_quantity": sum(item.quantity for item in items),
        "currency": settings_obj.currency_code,
        "currency_symbol": settings_obj.currency_symbol,
        "subtotal": str(subtotal),
        "mrp_total": str(mrp_total),
        "product_savings": str(max(Decimal("0.00"), mrp_total - subtotal)),
        "coupon_code": cart.coupon_code or None,
        "applied_promotion": best.as_dict() if best else None,
        "discount_amount": str(discount_amount),
        "discounted_subtotal": str(discounted_subtotal),
        "delivery_charge": str(delivery_charge),
        "is_free_delivery": delivery["is_free_delivery"],
        "free_delivery_threshold": str(delivery["free_delivery_threshold"]),
        "amount_to_free_delivery": str(delivery["amount_to_free_delivery"]),
        "packaging_charge": str(packaging),
        "tax_percent": str(round_money(settings_obj.default_tax_percent)),
        "tax_amount": str(tax_amount),
        "grand_total": str(grand_total),
        "minimum_order_value": str(round_money(settings_obj.minimum_order_value)),
        "minimum_order_met": subtotal >= round_money(settings_obj.minimum_order_value),
        "next_step": _next_step(issues, subtotal, settings_obj, items),
        "issues": issues,
        "store_open": settings_obj.is_store_open,
    }


def _collect_issues(cart, items, subtotal, settings_obj) -> list[dict]:
    """Problems that block checkout, surfaced to the client up front."""
    from common.utils import round_money

    issues = []
    if not settings_obj.is_store_open:
        issues.append(
            {
                "code": "store_closed",
                "message": settings_obj.maintenance_message
                or "The store is currently closed.",
            }
        )
    if not items:
        issues.append({"code": "empty_cart", "message": "Your cart is empty."})
        return issues

    minimum = round_money(settings_obj.minimum_order_value)
    if subtotal < minimum:
        issues.append(
            {
                "code": "below_minimum_order_value",
                "message": (
                    f"Add items worth ₹{round_money(minimum - subtotal)} more to "
                    f"reach the ₹{minimum} minimum order value."
                ),
                "minimum_order_value": str(minimum),
            }
        )

    for item in items:
        stock = getattr(item.product, "stock", None)
        if item.product.is_deleted or item.product.status != "active":
            issues.append(
                {
                    "code": "product_unavailable",
                    "message": f"'{item.product.name}' is no longer available.",
                    "product_id": item.product_id,
                }
            )
        elif stock is not None and stock.track_inventory and item.quantity > stock.quantity_available:
            issues.append(
                {
                    "code": "insufficient_stock",
                    "message": (
                        f"Only {stock.quantity_available} unit(s) of "
                        f"'{item.product.name}' remain in stock."
                    ),
                    "product_id": item.product_id,
                    "available": stock.quantity_available,
                    "requested": item.quantity,
                }
            )
        if item.price_changed:
            issues.append(
                {
                    "code": "price_changed",
                    "message": (
                        f"The price of '{item.product.name}' has changed to "
                        f"₹{item.product.selling_price}."
                    ),
                    "product_id": item.product_id,
                    "current_price": str(item.product.selling_price),
                    "cart_price": str(item.unit_price),
                }
            )
    return issues


def _next_step(issues, subtotal, settings_obj, items) -> str:
    codes = {issue["code"] for issue in issues}
    if "empty_cart" in codes:
        return "add_items"
    if "store_closed" in codes:
        return "store_closed"
    if "below_minimum_order_value" in codes:
        return "add_items"
    if "insufficient_stock" in codes or "product_unavailable" in codes:
        return "fix_cart"
    if "price_changed" in codes:
        return "review_prices"
    return "checkout"


def get_cart_or_404(identifier) -> Cart:
    from apps.cart.selectors import get_cart

    cart = get_cart(identifier)
    if cart is None:
        raise ResourceNotFoundError(
            message=f"Cart '{identifier}' was not found.", code="cart_not_found"
        )
    return cart


def get_cart_item_or_404(identifier) -> CartItem:
    from apps.cart.selectors import get_cart_item

    item = get_cart_item(identifier)
    if item is None:
        raise ResourceNotFoundError(
            message=f"Cart item '{identifier}' was not found.", code="cart_item_not_found"
        )
    return item


@transaction.atomic
def mark_cart_converted(cart: Cart, order) -> Cart:
    cart.status = CartStatus.CONVERTED
    cart.converted_order = order
    cart.coupon_code = ""
    cart.save(update_fields=["status", "converted_order", "coupon_code", "updated_at"])
    cart.items.all().delete()
    logger.info("Cart converted to order cart=%s order=%s", cart.id, order.id)
    return cart
