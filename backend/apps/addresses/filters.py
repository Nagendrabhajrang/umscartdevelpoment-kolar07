"""django-filter declarations for addresses."""

import django_filters

from apps.addresses.models import Address


class AddressFilter(django_filters.FilterSet):
    customer = django_filters.NumberFilter(field_name="customer_id")
    city = django_filters.CharFilter(lookup_expr="iexact")
    state = django_filters.CharFilter(lookup_expr="iexact")
    pincode = django_filters.CharFilter(lookup_expr="exact")
    is_default = django_filters.BooleanFilter()
    label = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = Address
        fields = ("customer", "city", "state", "pincode", "is_default", "label")
