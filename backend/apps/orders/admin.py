"""Django admin registration for orders."""

from django.contrib import admin
from django.utils.html import format_html

from apps.orders.models import Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = (
        "product", "product_name", "product_sku", "quantity", "unit_mrp",
        "unit_price", "line_total", "line_savings",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):  # noqa: D102
        return False


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    fields = ("from_status", "to_status", "note", "changed_by", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):  # noqa: D102
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number", "customer", "status", "payment_method", "payment_status",
        "_total", "item_count", "created_at",
    )
    list_filter = ("status", "payment_method", "payment_status", "created_at", "delivery_city")
    search_fields = (
        "order_number", "customer__full_name", "customer__mobile_number",
        "delivery_recipient_mobile",
    )
    list_select_related = ("customer",)
    readonly_fields = (
        "uid", "order_number", "confirmed_at", "delivered_at", "cancelled_at",
        "created_at", "updated_at",
    )
    inlines = [OrderItemInline, OrderStatusHistoryInline]
    date_hierarchy = "created_at"
    list_per_page = 40
    fieldsets = (
        ("Order", {"fields": ("order_number", "customer", "address", "status")}),
        ("Payment", {"fields": ("payment_method", "payment_status")}),
        (
            "Money",
            {
                "fields": (
                    "subtotal", "mrp_total", "product_savings", "discount_amount",
                    "coupon_code", "promotion_name", "delivery_charge",
                    "packaging_charge", "tax_amount", "grand_total", "currency",
                )
            },
        ),
        (
            "Delivery snapshot",
            {
                "fields": (
                    "delivery_recipient_name", "delivery_recipient_mobile",
                    "delivery_address_line1", "delivery_address_line2",
                    "delivery_landmark", "delivery_city", "delivery_state",
                    "delivery_pincode", "delivery_country", "delivery_instructions",
                )
            },
        ),
        ("Notes", {"fields": ("customer_notes", "internal_notes")}),
        (
            "Timeline",
            {"fields": ("confirmed_at", "delivered_at", "cancelled_at",
                        "cancellation_reason", "cancellation_note")},
        ),
    )

    @admin.display(description="Total", ordering="grand_total")
    def _total(self, obj):
        return format_html("<strong>₹{}</strong>", obj.grand_total)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product_name", "quantity", "unit_price", "line_total")
    search_fields = ("order__order_number", "product_name", "product_sku")
    list_select_related = ("order",)
    readonly_fields = tuple(field.name for field in OrderItem._meta.fields)

    def has_add_permission(self, request):  # noqa: D102
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: D102
        return False


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "from_status", "to_status", "changed_by", "created_at")
    list_filter = ("to_status", "created_at")
    search_fields = ("order__order_number", "note", "changed_by")
    readonly_fields = tuple(field.name for field in OrderStatusHistory._meta.fields)

    def has_add_permission(self, request):  # noqa: D102
        return False
