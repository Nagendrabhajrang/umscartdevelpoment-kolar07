"""Django admin registration for banners."""

from django.contrib import admin
from django.utils.html import format_html

from apps.banners.models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "placement", "_preview", "display_order", "is_active",
        "start_date", "end_date", "click_count", "view_count",
    )
    list_filter = ("placement", "is_active", "link_type")
    search_fields = ("title", "subtitle", "alt_text")
    readonly_fields = ("uid", "click_count", "view_count", "created_at", "updated_at")
    list_editable = ("display_order", "is_active")
    ordering = ("display_order",)

    @admin.display(description="Preview")
    def _preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:36px;border-radius:4px;" />', obj.image.url
            )
        return "-"
