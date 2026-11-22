"""Read-only queries for wishlists."""

from django.db.models import Prefetch, QuerySet

from apps.wishlist.models import Wishlist, WishlistItem
from common.selectors import id_or_uid_q


def wishlist_item_queryset() -> QuerySet[WishlistItem]:
    return WishlistItem.objects.select_related(
        "product", "product__category", "product__stock"
    )


def list_wishlists(customer=None) -> QuerySet[Wishlist]:
    queryset = Wishlist.objects.select_related("customer").prefetch_related(
        Prefetch("items", queryset=wishlist_item_queryset())
    )
    if customer is not None:
        queryset = queryset.filter(customer_id=getattr(customer, "id", customer))
    return queryset


def get_wishlist(identifier) -> Wishlist | None:
    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return (
        Wishlist.objects.select_related("customer")
        .prefetch_related(Prefetch("items", queryset=wishlist_item_queryset()))
        .filter(query)
        .first()
    )


def get_default_wishlist(customer) -> Wishlist | None:
    return (
        Wishlist.objects.filter(
            customer_id=getattr(customer, "id", customer), is_default=True
        )
        .prefetch_related(Prefetch("items", queryset=wishlist_item_queryset()))
        .first()
    )


def get_wishlist_item(identifier) -> WishlistItem | None:
    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return wishlist_item_queryset().filter(query).first()


def is_product_wishlisted(customer, product) -> bool:
    return WishlistItem.objects.filter(
        wishlist__customer_id=getattr(customer, "id", customer),
        product_id=getattr(product, "id", product),
    ).exists()


def wishlist_summary(customer=None) -> dict:
    queryset = list_wishlists(customer)
    from django.db.models import Count

    aggregate = queryset.aggregate(total_wishlists=Count("id"))
    aggregate["total_items"] = WishlistItem.objects.filter(
        wishlist__in=queryset
    ).count()
    return aggregate
