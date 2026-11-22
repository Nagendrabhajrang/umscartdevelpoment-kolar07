"""Django admin registration for carts."""

from django.contrib import admin

from apps.cart.models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    fields = ("product", "quantity", "unit_price", "unit_mrp", "notes")
    readonly_fields = ("added_at",)
    autocomplete_fields = ("product",)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        "id", "customer", "status", "coupon_code", "item_count", "last_activity_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("customer__full_name", "customer__mobile_number", "coupon_code")
    list_select_related = ("customer",)
    readonly_fields = ("uid", "created_at", "updated_at", "last_activity_at")
    inlines = [CartItemInline]
    ordering = ("-last_activity_at",)

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.items.count()


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product", "quantity", "unit_price", "added_at")
    search_fields = ("product__name", "cart__customer__mobile_number")
    list_select_related = ("cart", "product")
    readonly_fields = ("uid", "created_at", "updated_at", "added_at")
