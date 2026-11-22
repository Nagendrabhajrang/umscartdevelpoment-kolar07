"""Payment business logic: UPI proof submission, manual verification, COD.

Every state change locks the payment row (``SELECT FOR UPDATE``) so an admin
approving while a customer resubmits cannot corrupt the record, and each change
appends an immutable :class:`PaymentVerification` row.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order, OrderStatus, PaymentStatus as OrderPaymentStatus
from apps.payments.models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    PaymentVerification,
    Refund,
    RefundStatus,
    VerificationAction,
)
from common.exceptions import BusinessRuleError, ConflictError, ResourceNotFoundError
from common.utils import round_money

logger = logging.getLogger("apps.payments")


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------
@transaction.atomic
def create_payment_for_order(order: Order) -> Payment:
    """Create the payment record for a freshly placed order.

    Called by the checkout service inside its own transaction.
    """
    # Cash on delivery is the only method in this build.
    status_value = PaymentStatus.PENDING

    payment = Payment.objects.create(
        order=order,
        customer_id=order.customer_id,
        payment_method=PaymentMethod.COD,
        payment_status=status_value,
        amount=round_money(order.grand_total),
        currency=order.currency,
    )
    PaymentVerification.objects.create(
        payment=payment,
        action=VerificationAction.SUBMITTED,
        from_status="",
        to_status=status_value,
        remarks="Payment record created at checkout",
        performed_by="system",
    )
    logger.info(
        "Payment created number=%s order=%s method=%s amount=%s",
        payment.payment_number, order.order_number, payment.payment_method, payment.amount,
    )
    return payment


# ---------------------------------------------------------------------------
# UPI (removed)
# ---------------------------------------------------------------------------
# UPI was dropped from this build: every payment is cash on delivery. The
# model keeps transaction_id / upi_id so a future UPI phase can be re-enabled
# without another migration. These stubs keep the call sites honest instead of
# silently doing nothing.
def get_upi_details(payment: Payment) -> dict:
    raise BusinessRuleError(
        message="UPI payments are not enabled. This store is cash on delivery only.",
        code="upi_not_enabled",
    )


def submit_payment_proof(payment: Payment, *, transaction_reference: str,
                         proof=None, payer_name: str = "",
                         payer_upi_id: str = "", notes: str = "") -> Payment:
    raise BusinessRuleError(
        message="UPI payments are not enabled. This store is cash on delivery only.",
        code="upi_not_enabled",
    )


def approve_payment(payment: Payment, *, verified_by: str, remarks: str = "") -> Payment:
    raise BusinessRuleError(
        message="Manual payment approval is not used for cash on delivery. "
                "Record the cash with /cod-collected/ instead.",
        code="upi_not_enabled",
    )


def reject_payment(payment: Payment, *, reason: str, verified_by: str) -> Payment:
    raise BusinessRuleError(
        message="Rejecting a payment only applies to UPI, which is not enabled.",
        code="upi_not_enabled",
    )


# ---------------------------------------------------------------------------
# COD flow
# ---------------------------------------------------------------------------
@transaction.atomic
def mark_cod_collected(payment: Payment, *, amount=None, collected_by: str = "",
                       remarks: str = "", transaction_id: str = "",
                       mobile_number: str = "", feedback: str = "",
                       upi_id: str = "") -> Payment:
    """Mark cash as collected (normally at delivery).

    `transaction_id` records the payer's mobile number for this build;
    `upi_id` is accepted and stored so an existing form keeps working if UPI
    returns. Both are optional.
    """
    locked = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)

    if locked.payment_method != PaymentMethod.COD:
        raise BusinessRuleError(
            message="Only cash-on-delivery payments can be marked as collected.",
            code="not_a_cod_payment",
        )
    if locked.payment_status in {PaymentStatus.PAID, PaymentStatus.COLLECTED}:
        raise ConflictError(
            message="This cash payment is already recorded as collected.",
            code="payment_already_collected",
        )

    collected = round_money(amount if amount is not None else locked.amount)
    if collected != round_money(locked.amount):
        raise BusinessRuleError(
            message=(
                f"The collected amount must equal the payable amount "
                f"({locked.amount})."
            ),
            code="amount_mismatch",
            details={"expected": str(locked.amount), "received": str(collected)},
        )

    previous = locked.payment_status
    locked.payment_status = PaymentStatus.PAID
    locked.paid_at = timezone.now()
    locked.verified_by = collected_by or "delivery_agent"
    locked.verified_at = locked.paid_at
    if transaction_id:
        locked.transaction_id = transaction_id
    if mobile_number:
        locked.mobile_number = mobile_number
    if feedback:
        locked.feedback = feedback
    if upi_id:
        locked.upi_id = upi_id
    locked.save()

    order = locked.order
    order.payment_status = OrderPaymentStatus.COD_COLLECTED
    order.save(update_fields=["payment_status", "updated_at"])

    PaymentVerification.objects.create(
        payment=locked,
        action=VerificationAction.COLLECTED,
        from_status=previous,
        to_status=locked.payment_status,
        remarks=remarks or f"Cash collected: {collected}",
        performed_by=collected_by or "delivery_agent",
    )

    logger.info("COD collected %s amount=%s", locked.payment_number, collected)
    return locked


# ---------------------------------------------------------------------------
# Refunds & cancellation hooks
# ---------------------------------------------------------------------------
@transaction.atomic
def create_refund(payment: Payment, *, amount, reason: str = "",
                  feedback: str = "", processed_by: str = "") -> Refund:
    locked = Payment.objects.select_for_update().get(pk=payment.pk)
    if not locked.is_settled:
        raise BusinessRuleError(
            message="Only settled payments can be refunded.",
            code="payment_not_settled",
        )
    amount = round_money(amount)
    already = sum(
        (refund.amount for refund in locked.refunds.filter(status=RefundStatus.PROCESSED)),
        Decimal("0.00"),
    )
    if amount <= 0:
        raise BusinessRuleError(message="Refund amount must be positive.",
                                code="invalid_refund_amount")
    if already + amount > locked.amount:
        raise BusinessRuleError(
            message="The refund exceeds the paid amount.",
            code="refund_exceeds_payment",
            details={
                "paid": str(locked.amount),
                "already_refunded": str(already),
                "requested": str(amount),
            },
        )

    refund = Refund.objects.create(
        payment=locked, amount=amount, reason=reason or "", feedback=feedback or "",
        status=RefundStatus.PROCESSED, processed_at=timezone.now(), processed_by=processed_by or "",
    )
    PaymentVerification.objects.create(
        payment=locked,
        action=VerificationAction.REFUNDED,
        from_status=locked.payment_status,
        to_status=locked.payment_status,
        remarks=f"Refund {amount} processed: {reason or feedback or '-'}",
        performed_by=processed_by or "admin",
    )
    total_refunded = already + amount
    if total_refunded >= locked.amount:
        locked.payment_status = PaymentStatus.REFUNDED
        locked.save(update_fields=["payment_status", "updated_at"])
        locked.order.payment_status = OrderPaymentStatus.REFUNDED
        locked.order.save(update_fields=["payment_status", "updated_at"])

    logger.info("Refund created payment=%s amount=%s", locked.payment_number, amount)
    return refund


@transaction.atomic
def mark_order_cancelled(order: Order) -> None:
    """Hook called by the orders service when an order is cancelled."""
    payment = Payment.objects.select_for_update().filter(order=order).first()
    if payment is None:
        return
    if payment.payment_status in {PaymentStatus.PAID, PaymentStatus.VERIFIED,
                                 PaymentStatus.COLLECTED}:
        # Already paid - requires a refund decision by an admin; leave it alone.
        return
    previous = payment.payment_status
    payment.payment_status = PaymentStatus.CANCELLED
    payment.save(update_fields=["payment_status", "updated_at"])
    PaymentVerification.objects.create(
        payment=payment,
        action=VerificationAction.REJECTED,
        from_status=previous,
        to_status=payment.payment_status,
        remarks="Order cancelled - payment closed",
        performed_by="system",
    )


def get_payment_or_404(identifier) -> Payment:
    from apps.payments.selectors import get_payment

    payment = get_payment(identifier)
    if payment is None:
        raise ResourceNotFoundError(
            message=f"Payment '{identifier}' was not found.", code="payment_not_found"
        )
    return payment


def get_refund_or_404(identifier) -> Refund:
    from apps.payments.selectors import get_refund

    refund = get_refund(identifier)
    if refund is None:
        raise ResourceNotFoundError(
            message=f"Refund '{identifier}' was not found.", code="refund_not_found"
        )
    return refund
