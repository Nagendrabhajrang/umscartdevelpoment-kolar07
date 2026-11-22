"""Read-only queries for inventory."""

from django.db.models import F, Q, QuerySet

from apps.inventory.models import InventoryLog, Stock
from common.selectors import id_or_uid_q


def list_stock(filters: dict | None = None) -> QuerySet[Stock]:
    queryset = Stock.objects.select_related("product", "product__category")
    filters = filters or {}

    search = filters.get("search")
    if search:
        queryset = queryset.filter(
            Q(product__name__icontains=search)
            | Q(product__sku__icontains=search)
            | Q(product__brand__icontains=search)
        )

    category = filters.get("category")
    if category:
        queryset = queryset.filter(product__category_id=category)

    if filters.get("low_stock"):
        queryset = queryset.filter(
            quantity=F("quantity"),
            quantity__lte=F("low_stock_threshold"),
        )
    if filters.get("out_of_stock"):
        queryset = queryset.filter(quantity__lte=0)

    return queryset


def get_stock(product) -> Stock | None:
    product_id = getattr(product, "id", product)
    return Stock.objects.select_related("product").filter(product_id=product_id).first()


def get_stock_or_uid(identifier) -> Stock | None:
    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return Stock.objects.select_related("product").filter(query).first()


def list_movements(filters: dict | None = None) -> QuerySet[InventoryLog]:
    queryset = InventoryLog.objects.select_related("product", "stock")
    filters = filters or {}

    product = filters.get("product")
    if product:
        queryset = queryset.filter(product_id=product)
    movement_type = filters.get("movement_type")
    if movement_type:
        queryset = queryset.filter(movement_type=movement_type)
    reference = filters.get("reference")
    if reference:
        queryset = queryset.filter(reference__icontains=reference)
    if filters.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=filters["date_to"])
    return queryset


def low_stock_products(threshold: int | None = None) -> QuerySet[Stock]:
    queryset = Stock.objects.select_related("product").filter(
        track_inventory=True, quantity__lte=F("low_stock_threshold")
    )
    if threshold is not None:
        queryset = queryset.filter(quantity__lte=threshold)
    return queryset.order_by("quantity")


def inventory_summary() -> dict:
    from django.db.models import Count, Sum

    aggregate = Stock.objects.aggregate(
        total_products=Count("id"),
        total_units=Sum("quantity"),
        out_of_stock=Count("id", filter=Q(quantity__lte=0)),
        low_stock=Count("id", filter=Q(quantity__lte=F("low_stock_threshold"), quantity__gt=0)),
    )
    return {
        "total_products": aggregate["total_products"] or 0,
        "total_units": aggregate["total_units"] or 0,
        "out_of_stock": aggregate["out_of_stock"] or 0,
        "low_stock": aggregate["low_stock"] or 0,
    }
