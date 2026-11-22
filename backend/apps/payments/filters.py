"""django-filter declarations for payments."""

import django_filters

from apps.payments.models import Payment, PaymentVerification, Refund


class PaymentFilter(django_filters.FilterSet):
    # Query names are unchanged for API compatibility; they map to the
    # renamed columns (payment_status / payment_method).
    status = django_filters.CharFilter(field_name="payment_status", lookup_expr="iexact")
    method = django_filters.CharFilter(field_name="payment_method", lookup_expr="iexact")
    customer = django_filters.NumberFilter(field_name="customer_id")
    order = django_filters.NumberFilter(field_name="order_id")
    order_number = django_filters.CharFilter(field_name="order__order_number", lookup_expr="icontains")
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    min_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    max_amount = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")

    class Meta:
        model = Payment
        fields = ("customer", "order")


class PaymentVerificationFilter(django_filters.FilterSet):
    payment = django_filters.NumberFilter(field_name="payment_id")
    action = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = PaymentVerification
        fields = ("payment", "action")


class RefundFilter(django_filters.FilterSet):
    payment = django_filters.NumberFilter(field_name="payment_id")
    status = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = Refund
        fields = ("payment", "status")
