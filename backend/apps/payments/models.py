"""Payment models: Cash on Delivery only.

UPI was removed from this build. Payments are cash, collected at the door:

* The payment record is created at checkout with ``payment_status=pending``.
* When the delivery is completed the rider collects cash and an admin records
  it, moving the payment to ``paid`` (``payment_status``) and the order's
  payment status to ``cod_collected``.
* Every decision is appended to :class:`PaymentVerification`, an immutable
  audit trail.

Field naming follows the agreed specification:

============ =========================================================
``id``        primary key (auto)
``order``     FK -> Order
``customer``  FK -> Customer
``payment_method``  cod
``transaction_id``  UPI reference, kept for future use (blank for COD)
``amount``    amount to collect
``payment_status`` pending / approved / rejected / paid
``payment_proof``   optional screenshot
``upi_id``    customer UPI id, if provided
``verified_by``     admin who verified
``verified_at``     when verification happened
``rejection_reason`` why a payment was rejected
``paid_at``   when cash was actually collected
``created_at`` / ``updated_at``
============ =========================================================
"""


from django.db import models

from common.models import BaseModel
from common.utils import unique_reference
from common.validators import validate_document_file, validate_upi_id


class PaymentStatus(models.TextChoices):
    """The four states the spec asks for, plus the legacy aliases below."""

    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    PAID = "paid", "Paid"

    # --- aliases kept so older records and code keep working ----------------
    AWAITING_VERIFICATION = "awaiting_verification", "Awaiting verification"
    VERIFIED = "verified", "Verified"
    COLLECTED = "collected", "Cash collected"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"
    CANCELLED = "cancelled", "Cancelled"


class PaymentMethod(models.TextChoices):
    COD = "cod", "Cash on delivery"


class VerificationAction(models.TextChoices):
    SUBMITTED = "submitted", "Record created"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    RESUBMITTED = "resubmitted", "Resubmitted"
    COLLECTED = "collected", "Cash collected"
    REFUNDED = "refunded", "Refunded"


class Payment(BaseModel):
    """One payment record per order."""

    # -- 1/2/3: identity and relationships ----------------------------------
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="payments"
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="payments"
    )

    # -- 4: method ----------------------------------------------------------
    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, db_index=True, default="cod"
    )

    # -- 5: UPI reference (kept for future use; blank for COD) --------------
    transaction_id = models.CharField(
        max_length=120, blank=True, default="", db_index=True,
        help_text="UPI / transaction reference. Blank for cash payments.",
    )

    # -- 6: amount ----------------------------------------------------------
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")

    # -- 7: status ----------------------------------------------------------
    payment_status = models.CharField(
        max_length=25, choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING, db_index=True,
    )

    # -- 8: proof -----------------------------------------------------------
    payment_proof = models.FileField(
        upload_to="payments/proofs/%Y/%m/", null=True, blank=True,
        validators=[validate_document_file],
        help_text="Optional screenshot or PDF supporting the payment.",
    )
    payment_proof_uploaded_at = models.DateTimeField(null=True, blank=True)

    # -- 9: payer mobile ----------------------------------------------------
    mobile_number = models.CharField(
        max_length=20, blank=True, default="", db_index=True,
        help_text="Mobile number the cash was collected from / paid with.",
    )
    feedback = models.TextField(
        blank=True, default="",
        help_text="Free-form note captured by the admin (e.g. refund feedback).",
    )

    # -- 9b: legacy alternate mobile ---------------------------------------
    upi_id = models.CharField(
        max_length=120, blank=True, default="", validators=[validate_upi_id]
    )
    payer_name = models.CharField(max_length=150, blank=True, default="")

    # -- 10/11/12: verification --------------------------------------------
    verified_by = models.CharField(max_length=150, blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True, default="")
    verification_attempts = models.PositiveIntegerField(default=0)

    # -- 13: paid_at --------------------------------------------------------
    paid_at = models.DateTimeField(null=True, blank=True)

    # -- retained helpers ---------------------------------------------------
    collected_by = models.CharField(max_length=150, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    payment_number = models.CharField(
        max_length=40, unique=True, db_index=True, editable=False, blank=True
    )

    class Meta(BaseModel.Meta):
        db_table = "payments_payment"
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0), name="payment_amount_non_negative"
            ),
        ]
        indexes = [
            models.Index(fields=["payment_status", "payment_method"],
                         name="idx_payment_status_method"),
            models.Index(fields=["customer", "-created_at"], name="idx_payment_customer"),
            models.Index(fields=["order", "payment_status"], name="idx_payment_order_status"),
        ]

    def __str__(self) -> str:
        return f"{self.payment_number} ({self.payment_method}:{self.payment_status})"

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = unique_reference(
                Payment, "payment_number", "PAY", length=8
            )
        super().save(*args, **kwargs)

    # -- helpers ------------------------------------------------------------
    @property
    def is_settled(self) -> bool:
        return self.payment_status in {
            PaymentStatus.PAID, PaymentStatus.VERIFIED, PaymentStatus.COLLECTED,
        }

    @property
    def needs_verification(self) -> bool:
        return self.payment_status == PaymentStatus.AWAITING_VERIFICATION

    def get_absolute_url(self):
        return f"/api/v1/payments/{self.pk}/"


class RefundStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"


class PaymentVerification(BaseModel):
    """Immutable audit trail of every payment event."""

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name="verifications"
    )
    action = models.CharField(max_length=20, choices=VerificationAction.choices)
    from_status = models.CharField(max_length=25, blank=True, default="")
    to_status = models.CharField(max_length=25, blank=True, default="")
    transaction_reference = models.CharField(max_length=120, blank=True, default="")
    proof_file = models.FileField(
        upload_to="payments/verification/%Y/%m/", null=True, blank=True
    )
    remarks = models.CharField(max_length=255, blank=True, default="")
    performed_by = models.CharField(max_length=150, blank=True, default="system")

    class Meta(BaseModel.Meta):
        db_table = "payments_verification"
        verbose_name = "Payment verification"
        verbose_name_plural = "Payment verifications"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["payment", "-created_at"],
                         name="idx_paymentverify_payment"),
        ]

    def __str__(self) -> str:
        return f"{self.payment_id}: {self.action}"


class Refund(BaseModel):
    """A refund against a paid order (manual, recorded for accounting)."""

    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name="refunds"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True, default="")
    feedback = models.TextField(
        blank=True, default="",
        help_text="Free-form feedback supplied by the admin when refunding.",
    )
    status = models.CharField(
        max_length=20, choices=RefundStatus.choices, default=RefundStatus.PENDING,
        db_index=True,
    )
    reference = models.CharField(
        max_length=40, unique=True, db_index=True, editable=False
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.CharField(max_length=150, blank=True, default="")

    class Meta(BaseModel.Meta):
        db_table = "payments_refund"
        verbose_name = "Refund"
        verbose_name_plural = "Refunds"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.reference}: {self.payment_status}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = unique_reference(
                Refund, "reference", "RFD", length=8
            )
        super().save(*args, **kwargs)
