"""Django admin registration for wishlists."""

from django.contrib import admin

from apps.wishlist.models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0
    autocomplete_fields = ("product",)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "name", "is_default", "is_public", "created_at")
    list_filter = ("is_default", "is_public")
    search_fields = ("customer__full_name", "customer__mobile_number", "name")
    list_select_related = ("customer",)
    readonly_fields = ("uid", "created_at", "updated_at")
    inlines = [WishlistItemInline]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("id", "wishlist", "product", "created_at")
    search_fields = ("product__name", "wishlist__customer__mobile_number")
    list_select_related = ("wishlist", "product")
    readonly_fields = ("uid", "created_at", "updated_at")
