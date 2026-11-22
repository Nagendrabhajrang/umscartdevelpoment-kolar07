"""Read-only queries for carts."""

from django.db.models import Prefetch, QuerySet

from apps.cart.models import Cart, CartItem, CartStatus


def cart_item_queryset() -> QuerySet[CartItem]:
    return CartItem.objects.select_related(
        "product", "product__category", "product__stock"
    )


def list_carts(filters: dict | None = None) -> QuerySet[Cart]:
    queryset = Cart.objects.select_related("customer").prefetch_related(
        Prefetch("items", queryset=cart_item_queryset())
    )
    filters = filters or {}

    if filters.get("status"):
        queryset = queryset.filter(status=filters["status"])
    if filters.get("customer"):
        queryset = queryset.filter(customer_id=filters["customer"])
    if filters.get("coupon_code"):
        queryset = queryset.filter(coupon_code__iexact=filters["coupon_code"])

    search = filters.get("search")
    if search:
        queryset = queryset.filter(
            customer__full_name__icontains=search
        ) | queryset.filter(customer__mobile_number__icontains=search)

    return queryset


def get_cart(identifier) -> Cart | None:
    from common.selectors import id_or_uid_q

    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return (
        Cart.objects.select_related("customer")
        .prefetch_related(Prefetch("items", queryset=cart_item_queryset()))
        .filter(query)
        .first()
    )


def get_active_cart(customer) -> Cart | None:
    customer_id = getattr(customer, "id", customer)
    return (
        Cart.objects.filter(customer_id=customer_id, status=CartStatus.ACTIVE)
        .prefetch_related(Prefetch("items", queryset=cart_item_queryset()))
        .first()
    )


def get_cart_item(identifier) -> CartItem | None:
    from common.selectors import id_or_uid_q

    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return cart_item_queryset().filter(query).first()


def list_cart_items(cart: Cart) -> QuerySet[CartItem]:
    return cart.items.select_related("product", "product__category", "product__stock")


def cart_summary(filters: dict | None = None) -> dict:
    from django.db.models import Count, Q, Sum

    from apps.cart.models import CartItem

    carts = Cart.objects.all()
    aggregate = carts.aggregate(
        total_carts=Count("id"),
        active_carts=Count("id", filter=Q(status=CartStatus.ACTIVE)),
        abandoned_carts=Count("id", filter=Q(status=CartStatus.ABANDONED)),
        converted_carts=Count("id", filter=Q(status=CartStatus.CONVERTED)),
    )
    aggregate["total_items"] = CartItem.objects.count()
    aggregate["total_units"] = (
        CartItem.objects.aggregate(total=Sum("quantity"))["total"] or 0
    )
    return aggregate
