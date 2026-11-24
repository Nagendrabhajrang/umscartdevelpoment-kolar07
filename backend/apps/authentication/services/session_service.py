"""Session handling for the UMS Mart API.

Round 30: **Django sessions, not JWTs.**

Every previous round carried a token in the browser: an access token in
localStorage, a refresh token in an HttpOnly cookie, a rotation grace window, a
blacklist table. Each of those was a way for a perfectly healthy browser to end
up signed out - an expired access token read too eagerly, a refresh that failed
once, a cache miss on a rotation replay. The shopper saw "you have been signed
out" and never knew why.

Django already solves this: a session id in an HttpOnly cookie, a row in
``django_session``, and ``login()`` / ``logout()`` to manage it. There is no
token to expire while you read a page, no refresh to fail, and nothing for
JavaScript to store. The browser sends the cookie with every request and the
session either exists on the server or it does not.

This module keeps the *call shape* the views and services already use
(``start_session`` returns a payload dict, ``blacklist_all_for_user`` returns a
count) so the round-26..29 call sites did not have to be rewritten. What sits
behind those names is now Django's own machinery.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.accounts.models import User

logger = logging.getLogger(__name__)

#: Key under which the session records which role it was opened for. An admin
#: session must not silently act as a customer or vice versa - see
#: ``apps.authentication.authentication``.
SESSION_ROLE_KEY = "ums_role"
SESSION_USER_KEY = "_auth_user_id"


# ---------------------------------------------------------------------------
# Starting a session
# ---------------------------------------------------------------------------
def start_session(user: User, request=None) -> tuple[None, dict]:
    """Log ``user`` in, creating the Django session.

    Returns a 2-tuple for compatibility with the old token helper: the first
    element is still ``None`` (there is no session *object* to hand back) and the
    second is a small payload describing the identity. It deliberately contains
    **no credential**: the session id lives in an HttpOnly cookie the browser
    sends by itself, and nothing in JavaScript should ever see it.

    ``login()`` requires a request, because it needs somewhere to attach the
    session cookie and it must cycle the session key to prevent fixation. The
    request is always available from the DRF view; a missing one is a programming
    error rather than something to paper over.
    """
    if request is None:
        raise ValueError("start_session() needs the request to create a session")

    django_login(
        request,
        user,
        backend="apps.authentication.backends.OTPBackend",
    )

    # Pin the role into the session so a later change on the account can be
    # detected without trusting a client-supplied claim.
    request.session[SESSION_ROLE_KEY] = user.role
    request.session.modified = True

    return None, {"user": None}  # the caller fills in the user payload


def end_session(request) -> None:
    """Log this browser out, discarding its session on the server.

    ``logout()`` flushes the session - deleting the row, not merely clearing the
    cookie - so the id cannot be replayed afterwards.
    """
    if request is None:
        return

    # A sign-in that came through the bearer fallback has no cookie for
    # logout() to work with, so delete the session row the header names.
    bearer_key = getattr(request, "_ums_bearer_session_key", "")
    if bearer_key:
        from django.contrib.sessions.backends.db import SessionStore

        SessionStore(session_key=bearer_key).delete()

    django_logout(request)


def session_payload(request) -> dict:
    """What the client is allowed to know about its own session."""
    session = getattr(request, "session", None)
    if session is None:
        return {"expires_at": None, "age_seconds": None}

    expiry_age = getattr(session, "get_expiry_age", lambda: None)()
    return {
        "expires_at": (
            timezone.now() + timezone.timedelta(seconds=expiry_age)
            if expiry_age
            else None
        ),
        "age_seconds": expiry_age,
        "expire_at_browser_close": settings.SESSION_EXPIRE_AT_BROWSER_CLOSE,
    }


# ---------------------------------------------------------------------------
# Revocation
# ---------------------------------------------------------------------------
def _session_user_id(session: Session):
    """The user id stored in a session row, or ``None``.

    ``Session.get_decoded()`` can raise on a session written by an older
    ``SECRET_KEY`` or a corrupt row. A session that cannot be decoded identifies
    nobody, so it is not an error worth propagating.
    """
    try:
        return session.get_decoded().get(SESSION_USER_KEY)
    except Exception:  # pragma: no cover - corrupt or foreign-key-signed row
        return None


def blacklist_all_for_user(user: User) -> int:
    """Delete every active session belonging to ``user``. Returns the count.

    Used where "sign out everywhere" is the *point*: password reset, password
    change, and the explicit logout-all endpoint. It replaces the refresh-token
    blacklist, which could only ever invalidate a token - the session row would
    have stayed alive.

    Django has no indexed "sessions by user" table, so this walks the live rows.
    That is fine at this scale (expired rows are pruned by ``clearsessions``) and
    it is the documented approach.
    """
    if user is None or not getattr(user, "pk", None):
        return 0

    now = timezone.now()
    removed = 0

    for session in Session.objects.filter(expire_date__gt=now).iterator():
        if _session_user_id(session) == str(user.pk) or _session_user_id(
            session
        ) == user.pk:
            session.delete()
            removed += 1

    return removed


def active_session_count(user: User) -> int:
    """How many browsers this account is currently signed in on."""
    if user is None or not getattr(user, "pk", None):
        return 0

    now = timezone.now()
    count = 0
    for session in Session.objects.filter(expire_date__gt=now).iterator():
        uid = _session_user_id(session)
        if uid == str(user.pk) or uid == user.pk:
            count += 1
    return count


# ---------------------------------------------------------------------------
# Compatibility shims
# ---------------------------------------------------------------------------
def refresh_token_max_age():
    """Lifetime of a session, used by the cookie writer in the views."""
    return timezone.timedelta(seconds=settings.SESSION_COOKIE_AGE)


def new_session_id() -> str:
    """Kept only so old imports resolve.

    A session id is generated by Django inside ``login()`` and never leaves the
    HttpOnly cookie. Nothing should call this; it exists so a stale import fails
    loudly at review time rather than at import time.
    """
    raise RuntimeError(
        "new_session_id() is obsolete: Django now owns the session id and it is "
        "never exposed to JavaScript."
    )


def attach_session_token(payload: dict, request) -> dict:
    """Add ``session_token`` to a login response when the fallback is enabled.

    Used only where a session is *created* (customer OTP verify, admin password +
    MFA). When ``AUTH_BEARER_FALLBACK`` is off - i.e. everywhere except the
    sandbox preview - this is a no-op and no credential ever leaves the cookie.
    """
    from django.conf import settings

    if not getattr(settings, "AUTH_BEARER_FALLBACK", False):
        return payload
    session = getattr(request, "session", None)
    key = getattr(session, "session_key", None)
    if not key:
        return payload
    return {**payload, "session_token": key}
