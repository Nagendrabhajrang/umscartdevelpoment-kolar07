"""Wishlist business logic."""

import logging

from django.db import IntegrityError, transaction

from apps.wishlist.models import Wishlist, WishlistItem
from common.exceptions import (
    BusinessRuleError,
    ConflictError,
    ResourceNotFoundError,
)

logger = logging.getLogger("apps.wishlist")


def get_or_create_default_wishlist(customer) -> Wishlist:
    """Return the customer's default wishlist, creating it on first use.

    Same rule as the active cart: the INSERT gets its own atomic block so a
    lost race only rolls back the INSERT. Catching IntegrityError inside a
    shared transaction would leave it aborted and the recovery SELECT would
    raise TransactionManagementError instead of returning the row.
    """
    customer_id = getattr(customer, "id", customer)
    wishlist = Wishlist.objects.filter(
        customer_id=customer_id, is_default=True
    ).first()
    if wishlist:
        return wishlist
    try:
        with transaction.atomic():
            wishlist = Wishlist.objects.create(
                customer_id=customer_id, name="Default", is_default=True
            )
            # Read inside the atomic block on purpose: a failing INSERT must
            # not leave us holding a usable-but-poisoned transaction.
            wishlist.refresh_from_db()
        return wishlist
    except IntegrityError:
        # Another request created it first.
        return Wishlist.objects.get(customer_id=customer_id, is_default=True)


@transaction.atomic
def create_wishlist(customer, *, name: str, is_public: bool = False) -> Wishlist:
    name = (name or "").strip()
    if not name:
        raise BusinessRuleError(
            message="Wishlist name cannot be empty.", code="invalid_wishlist_name"
        )
    customer_id = getattr(customer, "id", customer)
    if Wishlist.objects.filter(customer_id=customer_id, name__iexact=name).exists():
        raise ConflictError(
            message="You already have a wishlist with this name.",
            code="duplicate_wishlist",
            details={"name": name},
        )
    wishlist = Wishlist.objects.create(
        customer_id=customer_id, name=name, is_public=is_public
    )
    logger.info("Wishlist created id=%s customer=%s", wishlist.id, customer_id)
    return wishlist


@transaction.atomic
def update_wishlist(wishlist: Wishlist, **data) -> Wishlist:
    name = data.get("name")
    if name:
        name = name.strip()
        if Wishlist.objects.filter(
            customer_id=wishlist.customer_id, name__iexact=name
        ).exclude(pk=wishlist.pk).exists():
            raise ConflictError(
                message="You already have a wishlist with this name.",
                code="duplicate_wishlist",
            )
        data["name"] = name
    for field_name, value in data.items():
        setattr(wishlist, field_name, value)
    wishlist.save()
    return wishlist


@transaction.atomic
def delete_wishlist(wishlist: Wishlist) -> None:
    if wishlist.is_default:
        raise BusinessRuleError(
            message="The default wishlist cannot be deleted.",
            code="default_wishlist_protected",
            status_code=409,
        )
    wishlist.delete()


@transaction.atomic
def add_to_wishlist(customer, product, *, wishlist: Wishlist | None = None,
                    notes: str = "") -> WishlistItem:
    wishlist = wishlist or get_or_create_default_wishlist(customer)
    if wishlist.customer_id != getattr(customer, "id", customer):
        raise BusinessRuleError(
            message="This wishlist belongs to another customer.",
            code="wishlist_forbidden",
            status_code=403,
        )
    if WishlistItem.objects.filter(wishlist=wishlist, product=product).exists():
        raise ConflictError(
            message=f"'{product.name}' is already in this wishlist.",
            code="duplicate_wishlist_item",
            details={"product_id": product.id},
        )
    item = WishlistItem.objects.create(
        wishlist=wishlist, product=product, notes=notes or ""
    )
    logger.info("Wishlist item added wishlist=%s product=%s", wishlist.id, product.id)
    return item


@transaction.atomic
def toggle_wishlist_item(customer, product) -> dict:
    """Add the product if absent, remove it if present. Returns the new state."""
    wishlist = get_or_create_default_wishlist(customer)
    existing = WishlistItem.objects.filter(wishlist=wishlist, product=product).first()
    if existing:
        existing.delete()
        logger.info("Wishlist item removed wishlist=%s product=%s", wishlist.id, product.id)
        return {"product_id": product.id, "is_wishlisted": False,
                "message": f"'{product.name}' removed from your wishlist."}
    WishlistItem.objects.create(wishlist=wishlist, product=product)
    logger.info("Wishlist item added wishlist=%s product=%s", wishlist.id, product.id)
    return {"product_id": product.id, "is_wishlisted": True,
            "message": f"'{product.name}' added to your wishlist."}


@transaction.atomic
def remove_wishlist_item(item: WishlistItem) -> None:
    item.delete()


@transaction.atomic
def move_to_cart(item: WishlistItem, quantity: int = 1):
    """Move a wishlist item into the customer's cart."""
    from apps.cart.services import add_to_cart

    cart_item = add_to_cart(item.wishlist.customer, item.product, quantity=quantity)
    item.delete()
    logger.info("Wishlist item moved to cart product=%s", item.product_id)
    return cart_item


def get_wishlist_or_404(identifier) -> Wishlist:
    from apps.wishlist.selectors import get_wishlist

    wishlist = get_wishlist(identifier)
    if wishlist is None:
        raise ResourceNotFoundError(
            message=f"Wishlist '{identifier}' was not found.", code="wishlist_not_found"
        )
    return wishlist


def get_wishlist_item_or_404(identifier) -> WishlistItem:
    from apps.wishlist.selectors import get_wishlist_item

    item = get_wishlist_item(identifier)
    if item is None:
        raise ResourceNotFoundError(
            message=f"Wishlist item '{identifier}' was not found.",
            code="wishlist_item_not_found",
        )
    return item
