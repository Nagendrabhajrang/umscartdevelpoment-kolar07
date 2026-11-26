"""Read-only queries for payments."""

from django.db.models import Prefetch, Count, Q, Sum, QuerySet
from django.utils import timezone

from apps.payments.models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    PaymentVerification,
    Refund,
)
from common.selectors import id_or_uid_q


def list_payments(filters: dict | None = None) -> QuerySet[Payment]:
    queryset = Payment.objects.select_related("order", "customer").prefetch_related(
        Prefetch("refunds", queryset=Refund.objects.order_by("-created_at"), to_attr="_refund_rows")
    )
    filters = filters or {}

    if filters.get("status"):
        queryset = queryset.filter(payment_status=filters["status"])
    if filters.get("method"):
        queryset = queryset.filter(payment_method=filters["method"])
    if filters.get("customer"):
        queryset = queryset.filter(customer_id=filters["customer"])
    if filters.get("order"):
        queryset = queryset.filter(order_id=filters["order"])
    if filters.get("order_number"):
        queryset = queryset.filter(order__order_number__icontains=filters["order_number"])
    if filters.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=filters["date_to"])

    search = filters.get("search")
    if search:
        queryset = queryset.filter(
            Q(payment_number__icontains=search)
            | Q(transaction_id__icontains=search)
            | Q(order__order_number__icontains=search)
            | Q(customer__full_name__icontains=search)
            | Q(customer__mobile_number__icontains=search)
        )
    return queryset


def get_payment(identifier) -> Payment | None:
    query = id_or_uid_q(identifier)
    if query is not None:
        found = (
            Payment.objects.select_related("order", "customer").filter(query).first()
        )
        if found:
            return found
    if identifier:
        return (
            Payment.objects.select_related("order", "customer")
            .filter(payment_number__iexact=str(identifier))
            .first()
        )
    return None


def get_payment_for_order(order) -> Payment | None:
    return (
        Payment.objects.select_related("order", "customer")
        .filter(order_id=getattr(order, "id", order))
        .order_by("-created_at")
        .first()
    )


def list_verifications(payment) -> QuerySet[PaymentVerification]:
    return payment.verifications.select_related("payment").all()


def pending_verifications() -> QuerySet[Payment]:
    """UPI payments waiting on an admin decision.

    Two statuses belong in this queue: ``awaiting_verification`` (order placed,
    customer has not submitted the UPI reference yet) and ``pending`` (reference
    submitted, admin has to check the bank statement). COD payments never
    appear here - cash is recorded at the door instead.
    """
    return Payment.objects.select_related("order", "customer").filter(
        payment_method=PaymentMethod.UPI,
        payment_status__in=[PaymentStatus.AWAITING_VERIFICATION, PaymentStatus.PENDING],
    ).order_by("created_at")


def list_refunds(filters: dict | None = None) -> QuerySet[Refund]:
    queryset = Refund.objects.select_related("payment", "payment__order")
    filters = filters or {}
    if filters.get("status"):
        queryset = queryset.filter(payment_status=filters["status"])
    if filters.get("payment"):
        queryset = queryset.filter(payment_id=filters["payment"])
    return queryset


def get_refund(identifier) -> Refund | None:
    query = id_or_uid_q(identifier)
    if query is None:
        return None
    return Refund.objects.select_related("payment").filter(query).first()


def payment_stats(filters: dict | None = None) -> dict:
    filters = filters or {}
    queryset = Payment.objects.all()
    if filters.get("date_from"):
        queryset = queryset.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        queryset = queryset.filter(created_at__date__lte=filters["date_to"])

    settled = queryset.filter(
        payment_status__in=[PaymentStatus.PAID, PaymentStatus.VERIFIED,
                            PaymentStatus.COLLECTED]
    )
    aggregate = queryset.aggregate(
        total_payments=Count("id"),
        total_amount=Sum("amount"),
        pending_verification=Count(
            "id",
            filter=Q(
                payment_method=PaymentMethod.UPI,
                payment_status__in=[
                    PaymentStatus.AWAITING_VERIFICATION, PaymentStatus.PENDING,
                ],
            ),
        ),
        rejected=Count("id", filter=Q(payment_status=PaymentStatus.REJECTED)),
        # Cash still to be collected. total - settled is wrong: it counts
        # refunded payments as "outstanding".
        pending_count=Count("id", filter=Q(payment_status=PaymentStatus.PENDING)),
        upi_payments=Count("id", filter=Q(payment_method=PaymentMethod.UPI)),
        cod_payments=Count("id", filter=Q(payment_method=PaymentMethod.COD)),
    )
    aggregate["settled_amount"] = settled.aggregate(total=Sum("amount"))["total"] or 0
    aggregate["settled_count"] = settled.count()
    aggregate["pending_count"] = aggregate.get("pending_count") or 0
    return aggregate


def awaiting_verification_older_than(hours: int) -> QuerySet[Payment]:
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(hours=hours)
    return Payment.objects.filter(
        payment_status=PaymentStatus.AWAITING_VERIFICATION, updated_at__lt=cutoff
    )
