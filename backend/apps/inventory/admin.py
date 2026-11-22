"""Django admin registration for inventory."""

from django.contrib import admin
from django.utils.html import format_html

from apps.inventory.models import InventoryLog, Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = (
        "product", "quantity", "reserved_quantity", "_available", "low_stock_threshold",
        "_status", "updated_at",
    )
    list_filter = ("track_inventory",)
    search_fields = ("product__name", "product__sku")
    list_select_related = ("product",)
    readonly_fields = ("uid", "created_at", "updated_at")
    ordering = ("product__name",)

    @admin.display(description="Available")
    def _available(self, obj):
        return obj.quantity_available

    @admin.display(description="Status")
    def _status(self, obj):
        if obj.is_out_of_stock:
            return format_html('<span style="color:#b91c1c;">Out of stock</span>')
        if obj.is_low_stock:
            return format_html('<span style="color:#b45309;">Low stock</span>')
        return format_html('<span style="color:#15803d;">In stock</span>')


@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "product", "movement_type", "quantity_change", "quantity_after",
        "reference", "created_at",
    )
    list_filter = ("movement_type", "created_at")
    search_fields = ("product__name", "product__sku", "reference", "reason")
    readonly_fields = tuple(
        field.name for field in InventoryLog._meta.fields
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request):  # noqa: D102
        return False

    def has_change_permission(self, request, obj=None):  # noqa: D102
        return False
