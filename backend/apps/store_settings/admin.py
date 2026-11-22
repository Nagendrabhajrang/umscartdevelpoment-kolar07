"""Django admin registration for store settings."""

from django.contrib import admin

from apps.store_settings.models import DeliverySlab, StoreHoliday, StoreSettings


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "store_name", "delivery_charge", "free_delivery_threshold",
        "minimum_order_value", "is_store_open", "cod_enabled", "upi_enabled",
    )
    readonly_fields = ("uid", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("store_name", "tagline", "contact_phone",
                                 "contact_email", "address")}),
        ("Currency", {"fields": ("currency_code", "currency_symbol")}),
        ("Delivery", {"fields": ("delivery_charge", "free_delivery_threshold",
                                 "minimum_order_value", "max_delivery_distance_km",
                                 "delivery_eta_minutes")}),
        ("Fees", {"fields": ("default_tax_percent", "packaging_charge",
                             "apply_tax_on_delivery")}),
        ("Orders", {"fields": ("cod_enabled", "upi_enabled", "max_items_per_order",
                               "order_prefix", "auto_cancel_unpaid_minutes")}),
        ("UPI", {"fields": ("upi_id", "upi_payee_name", "upi_qr_image")}),
        ("COD", {"fields": ("cod_instructions",)}),
        ("Status", {"fields": ("is_store_open", "maintenance_message")}),
    )

    def has_add_permission(self, request):  # noqa: D102
        return not StoreSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):  # noqa: D102
        return False


@admin.register(DeliverySlab)
class DeliverySlabAdmin(admin.ModelAdmin):
    list_display = (
        "name", "min_order_value", "max_order_value", "delivery_charge",
        "is_active", "display_order",
    )
    list_filter = ("is_active",)
    list_editable = ("is_active", "display_order")
    search_fields = ("name",)
    readonly_fields = ("uid", "created_at", "updated_at")


@admin.register(StoreHoliday)
class StoreHolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "reason", "is_active")
    list_filter = ("is_active",)
    search_fields = ("reason",)
    readonly_fields = ("uid", "created_at", "updated_at")
    date_hierarchy = "date"
