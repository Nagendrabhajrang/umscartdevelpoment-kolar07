"""django-filter declarations for the customers app."""

import django_filters

from apps.customers.models import Customer


class CustomerFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(lookup_expr="iexact")
    mobile_number = django_filters.CharFilter(lookup_expr="exact")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    has_orders = django_filters.BooleanFilter(method="filter_has_orders")

    class Meta:
        model = Customer
        fields = ("status", "mobile_number", "is_mobile_verified")

    def filter_has_orders(self, queryset, name, value):
        return queryset.filter(orders__isnull=not value).distinct()
