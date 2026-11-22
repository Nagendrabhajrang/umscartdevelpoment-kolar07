"""django-filter declarations for inventory."""

import django_filters
from django.db.models import F

from apps.inventory.models import InventoryLog, Stock


class StockFilter(django_filters.FilterSet):
    product = django_filters.NumberFilter(field_name="product_id")
    category = django_filters.NumberFilter(field_name="product__category_id")
    track_inventory = django_filters.BooleanFilter()
    low_stock = django_filters.BooleanFilter(method="filter_low_stock")
    out_of_stock = django_filters.BooleanFilter(method="filter_out_of_stock")

    class Meta:
        model = Stock
        fields = ("product", "track_inventory")

    def filter_low_stock(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(quantity__lte=F("low_stock_threshold"))

    def filter_out_of_stock(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(quantity__lte=0)


class InventoryLogFilter(django_filters.FilterSet):
    product = django_filters.NumberFilter(field_name="product_id")
    movement_type = django_filters.CharFilter(lookup_expr="iexact")
    reference = django_filters.CharFilter(lookup_expr="icontains")
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = InventoryLog
        fields = ("product", "movement_type", "reference")
