"""django-filter declarations for banners."""

import django_filters

from apps.banners.models import Banner


class BannerFilter(django_filters.FilterSet):
    placement = django_filters.CharFilter(lookup_expr="iexact")
    is_active = django_filters.BooleanFilter()
    link_type = django_filters.CharFilter(lookup_expr="iexact")
    starts_after = django_filters.DateTimeFilter(field_name="start_date", lookup_expr="gte")
    ends_before = django_filters.DateTimeFilter(field_name="end_date", lookup_expr="lte")

    class Meta:
        model = Banner
        fields = ("placement", "is_active", "link_type")
