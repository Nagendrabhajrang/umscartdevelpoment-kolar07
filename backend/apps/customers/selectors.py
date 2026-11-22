"""Read-only queries for the customers app."""

from django.db.models import Count, Q, QuerySet

from apps.customers.models import Customer, CustomerStatus
from common.selectors import id_or_uid_q

SEARCH_FIELDS = ("full_name", "mobile_number", "email")


def list_customers(filters: dict | None = None) -> QuerySet[Customer]:
    """Return customers with their aggregate counters pre-computed."""
    queryset = Customer.objects.all()
    filters = filters or {}

    status_value = filters.get("status")
    if status_value:
        queryset = queryset.filter(status=status_value)

    search = filters.get("search")
    if search:
        query = Q()
        for field in SEARCH_FIELDS:
            query |= Q(**{f"{field}__icontains": search})
        queryset = queryset.filter(query)

    if filters.get("created_after"):
        queryset = queryset.filter(created_at__date__gte=filters["created_after"])
    if filters.get("created_before"):
        queryset = queryset.filter(created_at__date__lte=filters["created_before"])

    # NOTE: the annotation aliases are deliberately distinct from the Customer
    # properties ``order_count`` / ``address_count``. Annotating with the same
    # name shadows a property that has no setter and raises at runtime.
    return queryset.annotate(
        orders_total=Count("orders", distinct=True),
        addresses_total=Count("addresses", distinct=True),
    )


def get_customer(identifier) -> Customer | None:
    """Fetch a customer by numeric id or public UUID."""
    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return Customer.objects.filter(query).first()


def get_customer_by_id(identifier) -> Customer | None:
    return get_customer(identifier)


def get_customer_by_mobile(mobile_number: str) -> Customer | None:
    if not mobile_number:
        return None
    return Customer.objects.filter(mobile_number=mobile_number).first()


def get_active_customers() -> QuerySet[Customer]:
    return Customer.objects.filter(status=CustomerStatus.ACTIVE)


def customer_summary() -> dict:
    """Aggregate counters used by the admin dashboards."""
    return Customer.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status=CustomerStatus.ACTIVE)),
        blocked=Count("id", filter=Q(status=CustomerStatus.BLOCKED)),
        inactive=Count("id", filter=Q(status=CustomerStatus.INACTIVE)),
    )
