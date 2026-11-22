"""Django admin registration for addresses."""

from django.contrib import admin

from apps.addresses.models import Address


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "id", "customer", "label", "recipient_name", "city", "pincode", "is_default",
    )
    list_filter = ("label", "is_default", "city", "state")
    search_fields = (
        "customer__full_name", "customer__mobile_number", "recipient_name",
        "line1", "city", "pincode",
    )
    list_select_related = ("customer",)
    readonly_fields = ("uid", "created_at", "updated_at")
    autocomplete_fields = ("customer",)
