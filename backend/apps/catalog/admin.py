"""Django admin registration for the catalog app."""

from django.contrib import admin
from django.utils.html import format_html

from apps.catalog.models import Category, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "display_order", "is_primary", "preview")
    readonly_fields = ("preview",)

    @admin.display(description="Preview")
    def preview(self, obj):
        if obj and obj.image:
            return format_html('<img src="{}" style="height:60px;" />', obj.image.url)
        return "-"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "parent", "is_active", "is_featured", "display_order")
    list_filter = ("is_active", "is_featured", "parent")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("uid", "created_at", "updated_at")
    ordering = ("display_order", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "sku", "category", "brand", "mrp", "selling_price",
        "status", "is_featured",
    )
    list_filter = ("status", "is_featured", "is_vegetarian", "category")
    search_fields = ("name", "sku", "barcode", "brand")
    readonly_fields = ("uid", "slug", "sku", "created_at", "updated_at")
    inlines = [ProductImageInline]
    list_select_related = ("category",)
    ordering = ("-created_at",)
    list_per_page = 50


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "is_primary", "display_order")
    list_filter = ("is_primary",)
    search_fields = ("product__name", "alt_text")
    readonly_fields = ("uid", "created_at", "updated_at")
