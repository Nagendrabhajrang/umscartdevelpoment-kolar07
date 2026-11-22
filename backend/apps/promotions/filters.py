"""django-filter declarations for promotions."""

import django_filters

from apps.promotions.models import CouponRedemption, Promotion


class PromotionFilter(django_filters.FilterSet):
    code = django_filters.CharFilter(lookup_expr="iexact")
    is_active = django_filters.BooleanFilter()
    is_visible = django_filters.BooleanFilter()
    discount_type = django_filters.CharFilter(lookup_expr="iexact")
    category = django_filters.NumberFilter(field_name="category_id")
    starts_after = django_filters.DateTimeFilter(field_name="start_date", lookup_expr="gte")
    ends_before = django_filters.DateTimeFilter(field_name="end_date", lookup_expr="lte")

    class Meta:
        model = Promotion
        fields = ("code", "is_active", "is_visible", "discount_type", "category")


class CouponRedemptionFilter(django_filters.FilterSet):
    promotion = django_filters.NumberFilter(field_name="promotion_id")
    customer = django_filters.NumberFilter(field_name="customer_id")
    order = django_filters.NumberFilter(field_name="order_id")

    class Meta:
        model = CouponRedemption
        fields = ("promotion", "customer", "order")
