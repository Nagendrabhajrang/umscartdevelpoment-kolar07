"""Admin site registration.

Registered so the single admin account can be inspected and the bridged customer
profiles audited. Creation is deliberately *not* offered here for admins: the
only supported path is ``manage.py create_admin``, which enforces the
one-admin rule. ``has_add_permission`` returns False to keep the site from
becoming a second door.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomerProfile, User


class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    extra = 0
    can_delete = False
    verbose_name_plural = _("Linked commerce customer")
    readonly_fields = ("customer", "created_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (CustomerProfileInline,)
    list_display = ("username", "email", "mobile_number", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_staff", "is_email_verified", "is_mobile_verified")
    search_fields = ("username", "email", "mobile_number")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Identity"), {"fields": ("email", "mobile_number")}),
        (_("Role"), {"fields": ("role",)}),
        (
            _("Verification"),
            {"fields": ("is_email_verified", "is_mobile_verified")},
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Timestamps"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "role", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ("date_joined",)

    def has_add_permission(self, request):
        """Provisioning happens through ``create_admin``, not the admin site."""
        return False

    def has_delete_permission(self, request, obj=None):
        """The single admin account must not be removed by accident."""
        if obj is not None and getattr(obj, "role", None) == "ADMIN":
            return False
        return super().has_delete_permission(request, obj)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "customer", "created_at")
    search_fields = ("user__mobile_number", "user__email", "customer__mobile_number")
    readonly_fields = ("created_at",)
