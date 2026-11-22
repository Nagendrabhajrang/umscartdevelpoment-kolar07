"""Django admin registration for payments."""

from django.contrib import admin
from django.utils.html import format_html

from apps.payments.models import Payment, PaymentVerification, Refund


class PaymentVerificationInline(admin.TabularInline):
    model = PaymentVerification
    extra = 0
    can_delete = False
    fields = ("action", "from_status", "to_status", "transaction_reference",
              "remarks", "performed_by", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):  # noqa: D102
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "payment_number", "order", "customer", "payment_method",
        "payment_status", "_amount", "transaction_id", "created_at",
    )
    list_filter = ("payment_method", "payment_status", "created_at")
    search_fields = (
        "payment_number", "transaction_id", "order__order_number",
        "customer__full_name", "customer__mobile_number",
    )
    list_select_related = ("order", "customer")
    readonly_fields = (
        "uid", "payment_number", "verified_at", "payment_proof_uploaded_at",
        "paid_at", "created_at", "updated_at", "_proof_preview",
    )
    inlines = [PaymentVerificationInline]
    date_hierarchy = "created_at"

    @admin.display(description="Amount", ordering="amount")
    def _amount(self, obj):
        return f"₹{obj.amount}"

    @admin.display(description="Proof")
    def _proof_preview(self, obj):
        if obj.payment_proof:
            return format_html(
                '<a href="{}" target="_blank">View proof</a>', obj.payment_proof.url
            )
        return "-"


@admin.register(PaymentVerification)
class PaymentVerificationAdmin(admin.ModelAdmin):
    list_display = ("id", "payment", "action", "from_status", "to_status", "performed_by",
                    "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("payment__payment_number", "transaction_reference", "performed_by")
    readonly_fields = tuple(field.name for field in PaymentVerification._meta.fields)

    def has_add_permission(self, request):  # noqa: D102
        return False

    def has_change_permission(self, request, obj=None):  # noqa: D102
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("reference", "payment", "amount", "status", "processed_at")
    list_filter = ("status",)
    search_fields = ("reference", "payment__payment_number", "reason")
    readonly_fields = ("uid", "reference", "created_at", "updated_at")
