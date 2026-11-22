"""Role-based permission classes.

The role is read from the authenticated user row - never from the request body or
a client-supplied header - so a caller cannot claim admin by editing JSON.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole


class IsAdminRole(BasePermission):
    message = "This endpoint is for administrators only."
    code = "admin_only"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == UserRole.ADMIN)


class IsCustomerRole(BasePermission):
    message = "This endpoint is for customers only."
    code = "customer_only"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == UserRole.CUSTOMER)


class IsOwnerOrAdmin(BasePermission):
    """Object-level guard for objects carrying a ``user`` or ``customer`` field."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.role == UserRole.ADMIN:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "customer", None)
        if owner is None:
            return False
        if owner == user:
            return True
        profile = getattr(user, "customer_profile", None)
        return bool(profile and owner == profile.customer)
