"""django-filter declarations for the catalog app."""

import django_filters
from django.db.models import Q

from apps.catalog.models import Category, Product


class CategoryFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    is_active = django_filters.BooleanFilter()
    is_featured = django_filters.BooleanFilter()
    parent = django_filters.NumberFilter(field_name="parent_id")
    top_level = django_filters.BooleanFilter(
        field_name="parent", lookup_expr="isnull", label="Top level only"
    )

    class Meta:
        model = Category
        fields = ("is_active", "is_featured", "parent")


class ProductFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(method="filter_category")
    category_slug = django_filters.CharFilter(method="filter_category_slug")
    brand = django_filters.CharFilter(lookup_expr="iexact")
    status = django_filters.CharFilter(lookup_expr="iexact")
    min_price = django_filters.NumberFilter(field_name="selling_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="selling_price", lookup_expr="lte")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")
    is_featured = django_filters.BooleanFilter()
    is_vegetarian = django_filters.BooleanFilter()
    sku = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = Product
        fields = ("category", "brand", "status", "is_featured", "is_vegetarian")

    def filter_category(self, queryset, name, value):
        """Filtering by a parent category also returns its children's products."""
        from apps.catalog.selectors import get_category, get_descendant_ids

        category = get_category(value)
        if category is None:
            return queryset.none()
        return queryset.filter(category_id__in=get_descendant_ids(category))

    def filter_category_slug(self, queryset, name, value):
        from apps.catalog.selectors import get_category_by_slug, get_descendant_ids

        category = get_category_by_slug(value)
        if category is None:
            return queryset.none()
        return queryset.filter(category_id__in=get_descendant_ids(category))

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__quantity__gt=0)
        return queryset.filter(Q(stock__isnull=True) | Q(stock__quantity__lte=0))
