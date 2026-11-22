"""Serializers for payments."""

import re
from decimal import Decimal

from rest_framework import serializers

from apps.payments.models import (
    Payment,
    PaymentVerification,
    Refund,
)
from common.validators import validate_document_file



MOBILE_HELP = "Enter a 10-digit mobile number, optionally prefixed with +91."


def clean_mobile(value):
    """Normalise an Indian mobile number; raise if it is not one.

    Blank is allowed - the caller decides whether the field is required.
    """
    value = (value or "").strip()
    if not value:
        return value
    digits = re.sub(r"[\s\-()]", "", value)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if not (digits.isdigit() and len(digits) == 10):
        raise serializers.ValidationError(MOBILE_HELP)
    return value


class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    order_total = serializers.DecimalField(
        source="order.grand_total", max_digits=12, decimal_places=2, read_only=True
    )
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_mobile = serializers.CharField(source="customer.mobile_number", read_only=True)
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    payment_status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    # Human-friendly aliases for older clients.
    method = serializers.CharField(source="payment_method", read_only=True)
    method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    status = serializers.CharField(source="payment_status", read_only=True)
    status_display = serializers.CharField(
        source="get_payment_status_display", read_only=True
    )
    proof_url = serializers.SerializerMethodField()
    is_settled = serializers.BooleanField(read_only=True)
    is_refunded = serializers.SerializerMethodField()
    refund_amount = serializers.SerializerMethodField()
    refund_feedback = serializers.SerializerMethodField()
    refund_reason = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id", "uid", "payment_number", "order", "order_number", "order_total",
            "customer", "customer_name", "customer_mobile",
            "payment_method", "payment_method_display",
            "payment_status", "payment_status_display",
            "method", "method_display", "status", "status_display",
            "amount", "currency", "transaction_id", "mobile_number", "feedback",
            "upi_id", "payer_name",
            "payment_proof", "proof_url", "payment_proof_uploaded_at",
            "verified_by", "verified_at", "rejection_reason",
            "verification_attempts", "paid_at", "collected_by", "notes",
            "is_settled", "is_refunded", "refund_amount", "refund_feedback",
            "refund_reason", "created_at", "updated_at",
        )
        read_only_fields = fields

    def _refund(self, obj):
        """Latest refund on this payment, if any (uses the prefetch when present)."""
        rows = getattr(obj, "_refund_rows", None)
        if rows is None:
            rows = list(obj.refunds.all()) if hasattr(obj, "refunds") else []
        return rows[0] if rows else None

    def get_is_refunded(self, obj) -> bool:
        return self._refund(obj) is not None

    def get_refund_amount(self, obj):
        refund = self._refund(obj)
        return str(refund.amount) if refund else None

    def get_refund_feedback(self, obj) -> str:
        refund = self._refund(obj)
        return (refund.feedback or "") if refund else ""

    def get_refund_reason(self, obj) -> str:
        refund = self._refund(obj)
        return (refund.reason or "") if refund else ""

    def get_proof_url(self, obj) -> str | None:
        if not obj.payment_proof:
            return None
        request = self.context.get("request")
        try:
            url = obj.payment_proof.url
        except ValueError:
            return None
        return url  # relative: /media is proxied by the frontend


class PaymentProofSerializer(serializers.Serializer):
    """Customer submission of a UPI transaction reference and proof."""

    transaction_reference = serializers.CharField(max_length=120)
    payer_name = serializers.CharField(required=False, allow_blank=True, max_length=150, default="")
    upi_id = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    notes = serializers.CharField(required=False, allow_blank=True, max_length=1000, default="")
    payment_proof = serializers.FileField(required=False, allow_null=True)

    def validate_transaction_reference(self, value):
        value = (value or "").strip()
        if len(value) < 6:
            raise serializers.ValidationError(
                "Enter the complete UPI transaction reference (at least 6 characters)."
            )
        return value

    def validate_payment_proof(self, value):
        if value is not None:
            validate_document_file(value)
        return value


class PaymentApprovalSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    verified_by = serializers.CharField(max_length=150, default="admin")


class PaymentRejectionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
    verified_by = serializers.CharField(max_length=150, default="admin")

    def validate_reason(self, value):
        value = (value or "").strip()
        if len(value) < 3:
            raise serializers.ValidationError("Provide a clear rejection reason.")
        return value


class CodCollectedSerializer(serializers.Serializer):
    """Cash collection: transaction id + payer mobile + optional feedback.

    Everything except `mobile_number` is optional, so a plain cash collection
    still succeeds without typing anything.
    """

    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal("0")
    )
    collected_by = serializers.CharField(
        required=False, allow_blank=True, max_length=150, default=""
    )
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    transaction_id = serializers.CharField(
        required=False, allow_blank=True, max_length=120, default=""
    )
    mobile_number = serializers.CharField(required=False, allow_blank=True, max_length=20, default="")
    feedback = serializers.CharField(required=False, allow_blank=True, max_length=1000, default="")
    upi_id = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")

    def validate_mobile_number(self, value):
        return clean_mobile(value)


class PaymentReferenceSerializer(serializers.Serializer):
    """Edit the transaction id / mobile number / feedback on a payment.

    Every field is optional so a partial edit is possible, but at least one
    must be present. Nothing else about the payment can change here.
    """

    transaction_id = serializers.CharField(
        required=False, allow_blank=True, max_length=120
    )
    mobile_number = serializers.CharField(
        required=False, allow_blank=True, max_length=20
    )
    feedback = serializers.CharField(
        required=False, allow_blank=True, max_length=1000
    )

    def validate_mobile_number(self, value):
        return clean_mobile(value)


class PaymentVerificationSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    proof_url = serializers.SerializerMethodField()

    class Meta:
        model = PaymentVerification
        fields = (
            "id", "uid", "payment", "action", "action_display", "from_status",
            "to_status", "transaction_reference", "proof_url", "remarks",
            "performed_by", "created_at",
        )
        read_only_fields = fields

    def get_proof_url(self, obj) -> str | None:
        if not obj.proof_file:
            return None
        request = self.context.get("request")
        try:
            url = obj.proof_file.url
        except ValueError:
            return None
        return url  # relative: /media is proxied by the frontend


class RefundSerializer(serializers.ModelSerializer):
    payment_number = serializers.CharField(source="payment.payment_number", read_only=True)
    order_number = serializers.CharField(
        source="payment.order.order_number", read_only=True
    )

    class Meta:
        model = Refund
        fields = (
            "id", "uid", "payment", "payment_number", "order_number", "amount",
            "reason", "feedback", "status", "reference", "processed_at",
            "processed_by", "created_at", "updated_at",
        )
        read_only_fields = ("id", "uid", "reference", "processed_at", "created_at", "updated_at")


class RefundCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    feedback = serializers.CharField(required=False, allow_blank=True, max_length=1000, default="")
    processed_by = serializers.CharField(
        required=False, allow_blank=True, max_length=150, default="admin"
    )


class PaymentStatsSerializer(serializers.Serializer):
    total_payments = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    settled_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    settled_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    pending_verification = serializers.IntegerField()
    rejected = serializers.IntegerField()
    upi_payments = serializers.IntegerField()
    cod_payments = serializers.IntegerField()
