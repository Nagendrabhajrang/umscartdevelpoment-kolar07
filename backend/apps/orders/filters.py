"""django-filter declarations for orders."""

import django_filters

from apps.orders.models import Order


class OrderFilter(django_filters.FilterSet):
    customer = django_filters.NumberFilter(field_name="customer_id")
    order_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.CharFilter(method="filter_status")
    payment_status = django_filters.CharFilter(lookup_expr="iexact")
    payment_method = django_filters.CharFilter(lookup_expr="iexact")
    city = django_filters.CharFilter(field_name="delivery_city", lookup_expr="iexact")
    pincode = django_filters.CharFilter(field_name="delivery_pincode", lookup_expr="exact")
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    min_total = django_filters.NumberFilter(field_name="grand_total", lookup_expr="gte")
    max_total = django_filters.NumberFilter(field_name="grand_total", lookup_expr="lte")

    class Meta:
        model = Order
        fields = ("customer", "status", "payment_status", "payment_method")

    def filter_status(self, queryset, name, value):
        if not value:
            return queryset
        statuses = [item.strip() for item in str(value).split(",") if item.strip()]
        return queryset.filter(status__in=statuses)
