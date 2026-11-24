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
    # COD starts as cash-due; a UPI payment starts out awaiting proof, because
    # the customer has to scan the store QR and submit a reference first.
    is_upi = order.payment_method == PaymentMethod.UPI
    status_value = (
        PaymentStatus.AWAITING_VERIFICATION if is_upi else PaymentStatus.PENDING
    )

    payment = Payment.objects.create(
        order=order,
        customer_id=order.customer_id,
        payment_method=order.payment_method,
        payment_status=status_value,
        amount=round_money(order.grand_total),
        currency=order.currency,
    )
    PaymentVerification.objects.create(
        payment=payment,
        action=VerificationAction.SUBMITTED,
        from_status="",
        to_status=status_value,
        remarks=(
            "UPI payment created at checkout - awaiting customer reference"
            if is_upi
            else "Payment record created at checkout"
        ),
        performed_by="system",
    )
    logger.info(
        "Payment created number=%s order=%s method=%s amount=%s",
        payment.payment_number, order.order_number, payment.payment_method, payment.amount,
    )
    return payment


# ---------------------------------------------------------------------------
# UPI flow
# ---------------------------------------------------------------------------
UPI_SETTINGS_HELP = (
    "The store has not configured UPI yet. An admin must add a UPI ID and QR "
    "image in the admin console under Settings."
)


def get_upi_details(payment: Payment) -> dict:
    """Everything the customer needs on screen to pay this order by UPI.

    Returns the store's UPI ID, payee name and QR image URL plus the amount to
    pay, the order number to use as the transaction note, and the current
    payment status so the storefront knows whether to keep showing the
    "I have paid" form.
    """
    from apps.store_settings.models import StoreSettings

    if payment.payment_method != PaymentMethod.UPI:
        raise BusinessRuleError(
            message="This payment is cash on delivery; there is no UPI step.",
            code="not_a_upi_payment",
        )

    store = StoreSettings.load()
    return {
        "payment": payment.id,
        "payment_number": payment.payment_number,
        "order_number": payment.order.order_number,
        "amount": str(payment.amount),
        "currency": payment.currency,
        "payment_status": payment.payment_status,
        "upi_id": store.upi_id or "",
        "upi_payee_name": store.upi_payee_name or store.store_name,
        "upi_qr_image_url": (
            store.upi_qr_image.url if store.upi_qr_image else None
        ),
        "transaction_note": payment.order.order_number,
        "is_configured": bool(store.upi_id),
        "help": "" if store.upi_id else UPI_SETTINGS_HELP,
        "rejection_reason": payment.rejection_reason or "",
        "transaction_id": payment.transaction_id or "",
        "can_submit": payment.payment_status
        in {
            PaymentStatus.AWAITING_VERIFICATION,
            PaymentStatus.PENDING,
            PaymentStatus.REJECTED,
        },
    }


@transaction.atomic
def submit_payment_proof(payment: Payment, *, transaction_reference: str,
                         proof=None, payer_name: str = "",
                         payer_upi_id: str = "", payer_mobile: str = "",
                         notes: str = "") -> Payment:
    """Customer says "I paid": store the UPI reference and move to pending.

    Allowed from awaiting_verification (first submission), rejected (retry after
    an admin said the money never arrived) and pending (re-submission of a
    clearer screenshot). Anything already settled is a conflict.
    """
    locked = (
        Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
    )

    if locked.payment_method != PaymentMethod.UPI:
        raise BusinessRuleError(
            message="Proof submission only applies to UPI payments.",
            code="not_a_upi_payment",
        )
    if locked.payment_status in {
        PaymentStatus.PAID, PaymentStatus.VERIFIED, PaymentStatus.COLLECTED,
        PaymentStatus.REFUNDED, PaymentStatus.APPROVED,
    }:
        raise ConflictError(
            message="This payment is already settled, so no proof is needed.",
            code="payment_already_settled",
        )

    reference = (transaction_reference or "").strip()
    if len(reference) < 6:
        raise BusinessRuleError(
            message="Enter the complete UPI transaction reference (at least 6 characters).",
            code="invalid_transaction_reference",
        )

    previous = locked.payment_status
    already_submitted = previous in {PaymentStatus.PENDING, PaymentStatus.REJECTED}

    locked.transaction_id = reference
    if payer_name:
        locked.payer_name = payer_name[:150]
    if payer_upi_id:
        locked.upi_id = payer_upi_id[:120]
    if payer_mobile:
        locked.mobile_number = payer_mobile[:20]
    if notes:
        locked.notes = (locked.notes + "\n" if locked.notes else "") + notes[:1000]
    if proof is not None:
        locked.payment_proof = proof
        locked.payment_proof_uploaded_at = timezone.now()
    locked.payment_status = PaymentStatus.PENDING
    locked.rejection_reason = ""
    locked.verification_attempts = (locked.verification_attempts or 0) + 1
    locked.save()

    order = locked.order
    order.payment_status = OrderPaymentStatus.PENDING_VERIFICATION
    order.save(update_fields=["payment_status", "updated_at"])

    PaymentVerification.objects.create(
        payment=locked,
        action=(
            VerificationAction.RESUBMITTED if already_submitted
            else VerificationAction.SUBMITTED
        ),
        from_status=previous,
        to_status=locked.payment_status,
        transaction_reference=reference,
        proof_file=proof if proof is not None else None,
        remarks=notes or "Customer submitted a UPI transaction reference",
        performed_by=f"customer:{locked.customer_id}",
    )

    logger.info(
        "UPI proof submitted payment=%s ref=%s", locked.payment_number, reference
    )
    return locked


@transaction.atomic
def approve_payment(payment: Payment, *, verified_by: str, remarks: str = "") -> Payment:
    """Admin confirms the money landed: payment paid, order paid."""
    locked = (
        Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
    )

    if locked.payment_method != PaymentMethod.UPI:
        raise BusinessRuleError(
            message=(
                "Manual approval is only for UPI payments. Record cash with "
                "/cod-collected/ instead."
            ),
            code="not_a_upi_payment",
        )
    if locked.payment_status in {PaymentStatus.PAID, PaymentStatus.APPROVED,
                                 PaymentStatus.VERIFIED, PaymentStatus.COLLECTED}:
        raise ConflictError(
            message="This payment is already approved.",
            code="payment_already_approved",
        )
    if locked.payment_status in {PaymentStatus.REFUNDED, PaymentStatus.CANCELLED}:
        raise BusinessRuleError(
            message="A refunded or cancelled payment cannot be approved.",
            code="payment_not_approvable",
        )
    if not locked.transaction_id:
        raise BusinessRuleError(
            message=(
                "The customer has not submitted a UPI reference yet, so there is "
                "nothing to verify."
            ),
            code="missing_transaction_reference",
        )

    previous = locked.payment_status
    now = timezone.now()
    locked.payment_status = PaymentStatus.PAID
    locked.paid_at = now
    locked.verified_by = (verified_by or "admin")[:150]
    locked.verified_at = now
    locked.rejection_reason = ""
    locked.save()

    order = locked.order
    order.payment_status = OrderPaymentStatus.PAID
    order.save(update_fields=["payment_status", "updated_at"])

    PaymentVerification.objects.create(
        payment=locked,
        action=VerificationAction.APPROVED,
        from_status=previous,
        to_status=locked.payment_status,
        transaction_reference=locked.transaction_id,
        remarks=remarks or "UPI payment verified against the bank statement",
        performed_by=locked.verified_by,
    )

    logger.info("UPI payment approved %s by=%s", locked.payment_number, locked.verified_by)
    return locked


@transaction.atomic
def reject_payment(payment: Payment, *, reason: str, verified_by: str) -> Payment:
    """Admin says the money did not arrive: back to the customer, with a reason."""
    locked = (
        Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
    )

    if locked.payment_method != PaymentMethod.UPI:
        raise BusinessRuleError(
            message="Rejecting a payment only applies to UPI payments.",
            code="not_a_upi_payment",
        )
    if locked.payment_status in {PaymentStatus.PAID, PaymentStatus.APPROVED,
                                 PaymentStatus.VERIFIED, PaymentStatus.COLLECTED}:
        raise ConflictError(
            message="This payment is already approved and cannot be rejected.",
            code="payment_already_approved",
        )

    previous = locked.payment_status
    locked.payment_status = PaymentStatus.REJECTED
    locked.rejection_reason = (reason or "")[:255]
    locked.verified_by = (verified_by or "admin")[:150]
    locked.verified_at = timezone.now()
    locked.save()

    order = locked.order
    order.payment_status = OrderPaymentStatus.UNPAID
    order.save(update_fields=["payment_status", "updated_at"])

    PaymentVerification.objects.create(
        payment=locked,
        action=VerificationAction.REJECTED,
        from_status=previous,
        to_status=locked.payment_status,
        transaction_reference=locked.transaction_id,
        remarks=locked.rejection_reason,
        performed_by=locked.verified_by,
    )

    logger.info("UPI payment rejected %s reason=%s", locked.payment_number, reason)
    return locked


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
