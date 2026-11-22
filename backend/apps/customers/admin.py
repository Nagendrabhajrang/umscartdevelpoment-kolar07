"""Django admin registration for customers."""

from django.contrib import admin

from apps.customers.models import Customer, CustomerNote


class CustomerNoteInline(admin.TabularInline):
    model = CustomerNote
    extra = 0
    fields = ("note", "author", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "mobile_number", "email", "status", "created_at")
    list_filter = ("status", "is_mobile_verified", "created_at")
    search_fields = ("full_name", "mobile_number", "email")
    readonly_fields = ("uid", "created_at", "updated_at", "last_login_at")
    inlines = [CustomerNoteInline]
    ordering = ("-created_at",)
    list_per_page = 50


@admin.register(CustomerNote)
class CustomerNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "author", "created_at")
    search_fields = ("customer__full_name", "customer__mobile_number", "note")
    readonly_fields = ("uid", "created_at", "updated_at")
