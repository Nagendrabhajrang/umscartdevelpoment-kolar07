"""Django admin registration for promotions."""

from django.contrib import admin

from apps.promotions.models import CouponRedemption, Promotion


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "code", "discount_type", "discount_value", "min_order_value",
        "is_active", "used_count", "start_date", "end_date",
    )
    list_filter = ("is_active", "is_visible", "discount_type", "applies_to")
    search_fields = ("name", "code", "description")
    filter_horizontal = ("products",)
    readonly_fields = ("uid", "used_count", "created_at", "updated_at")
    list_select_related = ("category",)
    fieldsets = (
        (None, {"fields": ("name", "code", "description", "is_active", "is_visible")}),
        (
            "Discount",
            {
                "fields": (
                    "discount_type", "discount_value", "max_discount_amount",
                    "min_order_value", "min_item_quantity",
                )
            },
        ),
        ("Targeting", {"fields": ("applies_to", "category", "products")}),
        ("Validity", {"fields": ("start_date", "end_date", "first_order_only")}),
        (
            "Usage",
            {
                "fields": (
                    "usage_limit_total", "usage_limit_per_customer", "used_count",
                    "priority", "display_order",
                )
            },
        ),
    )


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "promotion", "customer", "order", "discount_amount", "redeemed_at",
    )
    list_filter = ("redeemed_at",)
    search_fields = ("promotion__name", "promotion__code", "customer__mobile_number",
                     "order__order_number", "reference")
    readonly_fields = tuple(field.name for field in CouponRedemption._meta.fields)

    def has_add_permission(self, request):  # noqa: D102
        return False
