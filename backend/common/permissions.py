"""Permission classes.

Authentication and role-based authorisation are deliberately out of scope for
this phase (see ``docs/AUTHENTICATION.md``). These classes exist so the switch
to authenticated, role-aware permissions later is a one-line change per view:

    # today
    permission_classes = [AllowAny]

    # authentication phase
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]

Every view also carries a ``UMS Mart SECURITY NOTE`` docstring stating that the
endpoint must not be publicly exposed until authentication lands.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class ReadOnly(BasePermission):
    """Allows only safe (GET/HEAD/OPTIONS) requests."""

    message = "This endpoint is read-only."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class IsAdminOrReadOnlyPlaceholder(BasePermission):
    """Read for everyone, writes only for staff - the post-authentication default.

    Inactive during this phase because every request is anonymous, but kept
    and unit-tested so enabling it later requires no new code.
    """

    message = "Only administrators may modify this resource."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_staff)


class IsOwnerOrStaffPlaceholder(BasePermission):
    """Object level permission for customer-owned resources.

    The object must expose ``customer_id`` (directly or through ``order``).
    Inactive during this phase.
    """

    message = "You may only access your own records."

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        if user.is_staff:
            return True
        owner_id = getattr(obj, "customer_id", None)
        if owner_id is None and hasattr(obj, "order"):
            owner_id = getattr(obj.order, "customer_id", None)
        return owner_id == user.id
