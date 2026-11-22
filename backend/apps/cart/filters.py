"""django-filter declarations for carts."""

import django_filters

from apps.cart.models import Cart, CartItem


class CartFilter(django_filters.FilterSet):
    customer = django_filters.NumberFilter(field_name="customer_id")
    status = django_filters.CharFilter(lookup_expr="iexact")
    coupon_code = django_filters.CharFilter(lookup_expr="iexact")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Cart
        fields = ("customer", "status", "coupon_code")


class CartItemFilter(django_filters.FilterSet):
    cart = django_filters.NumberFilter(field_name="cart_id")
    product = django_filters.NumberFilter(field_name="product_id")

    class Meta:
        model = CartItem
        fields = ("cart", "product")
