"""Read-only queries for addresses."""

from django.db.models import QuerySet

from apps.addresses.models import Address
from common.selectors import id_or_uid_q


def list_addresses(filters: dict | None = None) -> QuerySet[Address]:
    queryset = Address.objects.select_related("customer")
    filters = filters or {}

    if filters.get("customer"):
        queryset = queryset.filter(customer_id=filters["customer"])
    if filters.get("city"):
        queryset = queryset.filter(city__iexact=filters["city"])
    if filters.get("pincode"):
        queryset = queryset.filter(pincode=filters["pincode"])
    if filters.get("is_default") is not None:
        queryset = queryset.filter(is_default=filters["is_default"])

    search = filters.get("search")
    if search:
        from django.db.models import Q

        queryset = queryset.filter(
            Q(recipient_name__icontains=search)
            | Q(line1__icontains=search)
            | Q(line2__icontains=search)
            | Q(city__icontains=search)
            | Q(pincode__icontains=search)
            | Q(customer__full_name__icontains=search)
            | Q(customer__mobile_number__icontains=search)
        )
    return queryset


def get_address(identifier) -> Address | None:
    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return Address.objects.select_related("customer").filter(query).first()


def get_addresses_for_customer(customer) -> QuerySet[Address]:
    return Address.objects.filter(customer_id=getattr(customer, "id", customer))


def get_default_address(customer) -> Address | None:
    return Address.objects.filter(
        customer_id=getattr(customer, "id", customer), is_default=True
    ).first()
