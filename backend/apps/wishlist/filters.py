"""django-filter declarations for wishlists."""

import django_filters

from apps.wishlist.models import Wishlist, WishlistItem


class WishlistFilter(django_filters.FilterSet):
    customer = django_filters.NumberFilter(field_name="customer_id")
    is_default = django_filters.BooleanFilter()
    is_public = django_filters.BooleanFilter()

    class Meta:
        model = Wishlist
        fields = ("customer", "is_default", "is_public")


class WishlistItemFilter(django_filters.FilterSet):
    wishlist = django_filters.NumberFilter(field_name="wishlist_id")
    product = django_filters.NumberFilter(field_name="product_id")
    customer = django_filters.NumberFilter(field_name="wishlist__customer_id")

    class Meta:
        model = WishlistItem
        fields = ("wishlist", "product")
