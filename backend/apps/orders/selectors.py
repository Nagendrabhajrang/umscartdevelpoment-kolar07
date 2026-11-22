"""Read-only queries for orders."""

from datetime import timedelta

from django.db.models import Count, Prefetch, Q, Sum, QuerySet
from django.utils import timezone

from apps.orders.models import (
    ACTIVE_ORDER_STATUSES,
    REVENUE_ORDER_STATUSES,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
)
from common.selectors import id_or_uid_q


def order_item_queryset() -> QuerySet[OrderItem]:
    return OrderItem.objects.select_related("product")


def order_base_queryset() -> QuerySet[Order]:
    return (
        Order.objects.select_related("customer", "address")
        .prefetch_related(Prefetch("items", queryset=order_item_queryset()))
    )


def list_orders(filters: dict | None = None) -> QuerySet[Order]:
    queryset = order_base_queryset()
    filters = filters or {}

    if filters.get("customer"):
        queryset = queryset.filter(customer_id=filters["customer"])
    if filters.get("status"):
        status_value = filters["status"]
        if isinstance(status_value, str) and "," in status_value:
            queryset = queryset.filter(status__in=[s.strip() for s in status_value.split(",")])
        else:
            queryset = queryset.filter(status=status_value)
    if filters.get("payment_status"):
        queryset = queryset.filter(payment_status=filters["payment_status"])
    if filters.get("payment_method"):
        queryset = queryset.filter(payment_method=filters["payment_method"])
    if filters.get("order_number"):
        queryset = queryset.filter(order_number__icontains=filters["order_number"])
    if filters.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=filters["date_to"])
    if filters.get("city"):
        queryset = queryset.filter(delivery_city__iexact=filters["city"])
    if filters.get("pincode"):
        queryset = queryset.filter(delivery_pincode=filters["pincode"])

    search = filters.get("search")
    if search:
        queryset = queryset.filter(
            Q(order_number__icontains=search)
            | Q(customer__full_name__icontains=search)
            | Q(customer__mobile_number__icontains=search)
            | Q(delivery_recipient_name__icontains=search)
            | Q(delivery_recipient_mobile__icontains=search)
        )
    return queryset


def get_order(identifier) -> Order | None:
    """Fetch an order by numeric id, public UUID or order number."""
    query = id_or_uid_q(identifier)
    if query is not None:
        found = order_base_queryset().filter(query).first()
        if found:
            return found
    if identifier:
        return order_base_queryset().filter(order_number__iexact=str(identifier)).first()
    return None


def get_orders_for_customer(customer, status=None) -> QuerySet[Order]:
    queryset = order_base_queryset().filter(customer_id=getattr(customer, "id", customer))
    if status:
        queryset = queryset.filter(status=status)
    return queryset


def get_active_orders_for_customer(customer) -> QuerySet[Order]:
    return order_base_queryset().filter(
        customer_id=getattr(customer, "id", customer),
        status__in=ACTIVE_ORDER_STATUSES,
    )


def get_order_items(order: Order) -> QuerySet[OrderItem]:
    return order.items.select_related("product").all()


def get_status_history(order: Order) -> QuerySet[OrderStatusHistory]:
    return order.status_history.all()


def order_stats(filters: dict | None = None) -> dict:
    """Aggregate order KPIs used by dashboards."""
    filters = filters or {}
    queryset = Order.objects.all()
    if filters.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=filters["date_to"])

    aggregate = queryset.aggregate(
        total_orders=Count("id"),
        revenue=Sum("grand_total", filter=Q(status__in=REVENUE_ORDER_STATUSES)),
        cancelled_orders=Count("id", filter=Q(status=OrderStatus.CANCELLED)),
        delivered_orders=Count("id", filter=Q(status=OrderStatus.DELIVERED)),
        pending_orders=Count("id", filter=Q(status=OrderStatus.PENDING)),
        cod_orders=Count("id", filter=Q(payment_method="cod")),
        upi_orders=Count("id", filter=Q(payment_method="upi")),
    )
    delivered = aggregate["delivered_orders"] or 0
    total = aggregate["total_orders"] or 0
    return {
        "total_orders": total,
        "total_revenue": str(aggregate["revenue"] or "0.00"),
        "cancelled_orders": aggregate["cancelled_orders"] or 0,
        "delivered_orders": delivered,
        "pending_orders": aggregate["pending_orders"] or 0,
        "cod_orders": aggregate["cod_orders"] or 0,
        "upi_orders": aggregate["upi_orders"] or 0,
        "average_order_value": (
            str((aggregate["revenue"] or 0) / delivered) if delivered else "0.00"
        ),
        "fulfilment_rate": round(delivered / total * 100, 2) if total else 0.0,
    }


def todays_orders() -> QuerySet[Order]:
    today = timezone.localdate()
    return order_base_queryset().filter(created_at__date=today)


def pending_payment_orders_older_than(minutes: int) -> QuerySet[Order]:
    """UPI orders still awaiting payment after ``minutes`` - auto-cancel fodder."""
    cutoff = timezone.now() - timedelta(minutes=minutes)
    return Order.objects.filter(
        payment_method="upi",
        payment_status__in=["unpaid", "pending_verification"],
        status=OrderStatus.PENDING,
        created_at__lt=cutoff,
    )
