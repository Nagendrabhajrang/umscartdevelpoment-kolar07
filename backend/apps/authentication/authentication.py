"""Authentication for the UMS Mart API.

Round 30: **Django session authentication.**

The browser holds one HttpOnly ``ums_mart_sessionid`` cookie. Django's
``SessionMiddleware`` turns it into ``request.user`` before DRF ever runs, and
DRF's ``SessionAuthentication`` is the only class configured. There is no token
to parse, no header to send, and no refresh step that can fail and sign a healthy
shopper out - which is exactly the failure this round exists to remove.

Two jobs are left for this module:

1. **Be forgiving on public endpoints.** ``SessionAuthentication`` answers 401
   when a request is not authenticated, but only when the view *requires* it.
   Public catalogue endpoints must keep serving an anonymous visitor.
2. **Keep roles honest.** A session records the role it was opened for. If the
   account's role changed underneath it, the session is refused rather than
   silently granting the old rights.
"""

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from rest_framework.authentication import SessionAuthentication, get_authorization_header

from apps.accounts.models import UserRole
from apps.authentication.services.session_service import SESSION_ROLE_KEY


def bearer_session_key(request) -> str:
    """Return the session key from an ``Authorization: Bearer <key>`` header.

    Empty string when the header is absent or is not a Bearer token.
    """
    if not getattr(settings, "AUTH_BEARER_FALLBACK", False):
        return ""
    parts = get_authorization_header(request).split()
    if len(parts) == 2 and parts[0].lower() == b"bearer":
        try:
            return parts[1].decode("ascii")
        except UnicodeDecodeError:
            return ""
    return ""


def user_from_session_key(session_key: str):
    """Resolve a session key to its user, or None if the session is gone."""
    if not session_key:
        return None
    from django.contrib.auth import SESSION_KEY
    from django.contrib.auth.models import AnonymousUser

    session = SessionStore(session_key=session_key)
    try:
        data = session.load()
    except Exception:  # pragma: no cover - corrupt/absent session row
        return None
    user_id = data.get(SESSION_KEY)
    if not user_id:
        return None

    from apps.accounts.models import User

    user = User.objects.filter(pk=user_id, is_active=True).first()
    return user or AnonymousUser()


class UmsSessionAuthentication(SessionAuthentication):
    """Session authentication with a role check.

    ``SessionAuthentication`` already refuses unsafe requests without a valid
    CSRF token, which is what makes cookie-based auth safe against cross-site
    form posts. Everything else - the cookie, the session row, expiry - is
    Django's.
    """

    def authenticate_header(self, request):
        """Make an unauthenticated request a **401**, not a 403.

        DRF decides between 401 and 403 by asking the authenticator for a
        ``WWW-Authenticate`` challenge. ``SessionAuthentication`` returns ``None``
        - reasonable in DRF's world, where a browser is expected to be redirected
        to a login page - so an anonymous request comes back **403**.

        That distinction is load-bearing for this app. The storefront must be able
        to say "the server confirmed you have no session, go to /login" and it
        keys that decision strictly on 401. If a missing session arrives as 403 it
        is indistinguishable from "you are signed in but not allowed to do that",
        and the client would leave the shopper on a page of permission errors.

        Advertising ``Session`` is honest: Django's session cookie is the scheme.
        """
        return 'Session realm="ums-mart"'

    def authenticate(self, request):
        # --- bearer fallback (cross-site frames where cookies are refused) ----
        header_key = bearer_session_key(request)
        if header_key:
            user = user_from_session_key(header_key)
            if user is None:
                return None
            from django.contrib.auth.models import AnonymousUser

            if isinstance(user, AnonymousUser):
                return None

            # The session the key names must have been opened for this role.
            opened_as = SessionStore(session_key=header_key).get(SESSION_ROLE_KEY)
            if opened_as and opened_as != user.role:
                return None

            # CSRF is deliberately NOT enforced here: the credential is an
            # explicit header, so a cross-site form post cannot carry it.
            request._ums_via_bearer = True
            request._ums_bearer_session_key = header_key
            return (user, None)

        # --- normal path: the Django session cookie --------------------------
        result = super().authenticate(request)
        if result is None:
            return None

        user, _auth = result

        # The role the session was opened with must still match the account.
        # A demoted admin must not keep admin rights on a session created
        # before the change.
        opened_as = request.session.get(SESSION_ROLE_KEY)
        if opened_as and opened_as != user.role:
            # Close the session rather than leave a half-valid identity behind.
            request.session.flush()
            return None

        return result


def role_required(role: str):
    """Build a DRF permission class that requires a specific role.

    Kept here next to the session code because the two must agree: a view that
    demands ``ADMIN`` must be paired with a session that was opened as an admin.
    ``apps.authentication.permissions`` has the concrete classes; this factory is
    for the occasional one-off.
    """
    from rest_framework.permissions import BasePermission

    class _RoleRequired(BasePermission):
        message = f"This endpoint is for {role.lower()} accounts only."
        code = f"{role.lower()}_only"

        def has_permission(self, request, view):
            user = request.user
            return bool(
                user and user.is_authenticated and user.role == role
            )

    return _RoleRequired


__all__ = ["UmsSessionAuthentication", "role_required", "UserRole"]
