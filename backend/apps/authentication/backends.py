"""Django's session authentication backend for the OTP login flow.

Django's ``ModelBackend`` authenticates with a username and password. Customers
and admins here authenticate with an OTP, and there is no password to check for a
customer at all. ``login()`` still insists on a backend, so this one exists to
say "the OTP flow already proved who this is".

It is not reachable through ``authenticate()`` on purpose: nothing should be able
to log a user in by calling ``authenticate(backend=...)`` without an OTP. The only
caller is ``session_service.start_session``, after verification has succeeded.
"""

from apps.accounts.models import User


class OTPBackend:
    """Marks a user as authenticated after an out-of-band (OTP) check."""

    def authenticate(self, request, **kwargs):  # pragma: no cover - never used
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
