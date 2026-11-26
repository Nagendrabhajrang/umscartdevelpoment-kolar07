"""Request-scoped middleware: correlation ids, logging and JSON error safety."""

import logging
import time
import uuid

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger("common.requests")
error_logger = logging.getLogger("common.errors")


class RequestLoggingMiddleware:
    """Attaches a request id and logs one line per API request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex

        started = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - started) * 1000

        response["X-Request-Id"] = request.request_id

        if request.path.startswith("/api/") or request.path.startswith("/health"):
            logger.info(
                "%s %s -> %s (%0.1f ms) ip=%s rid=%s",
                request.method,
                request.get_full_path(),
                getattr(response, "status_code", "-"),
                duration_ms,
                _client_ip(request),
                request.request_id,
            )
        return response


from django.contrib.sessions.middleware import SessionMiddleware


class ClientScopedSessionMiddleware(SessionMiddleware):
    """One host, two independent sessions: storefront and dashboard.

    Cookies are scoped to a **host**, not to a port. In development the storefront
    (localhost:5173) and the admin dashboard (localhost:5174) therefore share one
    cookie jar, and with a single ``ums_mart_sessionid`` they shared one session:
    signing in to the dashboard replaced the customer's session, the dashboard
    then owned the only session, and the storefront rendered "admin" as if the
    administrator were the shopper.

    The dashboard tags every request with ``X-Client: admin``. Those requests read
    and write ``ums_mart_admin_sessionid`` instead, so the two sessions are
    separate and neither login can disturb the other. Anything without the header
    - the storefront, API clients, the Django admin - keeps the existing cookie
    and sees no change at all.

    In production the two apps normally live on different hosts, where the browser
    already separates them; this makes development behave the same way.
    """

    ADMIN_COOKIE_NAME = "ums_mart_admin_sessionid"
    CLIENT_HEADER = "X-Client"

    def _cookie_name(self, request) -> str:
        client = (request.META.get("HTTP_X_CLIENT") or "").strip().lower()
        if client == "admin":
            return self.ADMIN_COOKIE_NAME
        return settings.SESSION_COOKIE_NAME

    def process_request(self, request):
        default = settings.SESSION_COOKIE_NAME
        name = self._cookie_name(request)
        if name == default:
            return super().process_request(request)

        # Hand the parent the admin cookie under the name it expects, then put the
        # browser's real cookie jar back: nothing downstream should see a request
        # whose cookies were quietly swapped.
        original = request.COOKIES.get(default)
        request.COOKIES[default] = request.COOKIES.get(name, "")
        try:
            return super().process_request(request)
        finally:
            if original is None:
                request.COOKIES.pop(default, None)
            else:
                request.COOKIES[default] = original

    def process_response(self, request, response):
        response = super().process_response(request, response)
        default = settings.SESSION_COOKIE_NAME
        name = self._cookie_name(request)
        if name == default or default not in response.cookies:
            return response

        # The parent wrote the cookie under the shared name; move it to the
        # client-specific one it actually came from. Rebuilt with set_cookie so
        # every attribute (HttpOnly, SameSite, Secure, expiry) survives - including
        # the already-expired cookie a logout sends.
        morsel = response.cookies.pop(default)
        max_age = morsel["max-age"]
        response.set_cookie(
            key=name,
            value=morsel.value,
            max_age=int(max_age) if str(max_age).isdigit() else None,
            expires=morsel["expires"] or None,
            path=morsel["path"] or "/",
            domain=morsel["domain"] or None,
            secure=bool(morsel["secure"]),
            httponly=bool(morsel["httponly"]),
            samesite=morsel["samesite"] or None,
        )
        return response


try:  # pragma: no cover - the guard is about Django upgrades, not behaviour
    from django.middleware.csrf import CsrfViewMiddleware as _DjangoCsrf
except Exception:  # pragma: no cover
    _DjangoCsrf = None


if _DjangoCsrf is not None and hasattr(_DjangoCsrf, "_origin_verified"):

    class DevOriginTolerantCsrfMiddleware(_DjangoCsrf):
        """CSRF middleware that accepts any local origin, in DEBUG only.

        Django verifies an unsafe cross-origin request by comparing its ``Origin``
        header against ``CSRF_TRUSTED_ORIGINS``. That setting cannot express "any
        port on this machine": the admin dashboard on 5174, a dev server that
        landed on 5175, or a phone opening the store over ``http://192.168.1.5:5174``
        all failed the check and the UI reported it as a rejected status change.

        In development the browser is not the attacker this defends against, so
        loopback and private-network origins are trusted. Production keeps the
        strict middleware untouched.
        """

        def _origin_verified(self, request):
            if super()._origin_verified(request):
                return True
            if not getattr(settings, "DEBUG", False):
                return False
            origin = request.META.get("HTTP_ORIGIN") or ""
            if not origin:
                return False
            try:
                from urllib.parse import urlsplit

                host = (urlsplit(origin).hostname or "").lower().rstrip(".")
            except Exception:  # pragma: no cover
                return False
            if not host:
                return False
            if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
                return True
            try:
                import ipaddress

                return ipaddress.ip_address(host).is_loopback or ipaddress.ip_address(host).is_private
            except ValueError:
                return False

else:  # pragma: no cover - very old/very new Django without the hook
    DevOriginTolerantCsrfMiddleware = _DjangoCsrf


class ApiExceptionMiddleware:
    """Guarantees that unexpected errors under /api/ return JSON, never HTML.

    DRF's exception handler already covers exceptions raised inside DRF views;
    this catches the remaining cases (middleware level failures, Django 500s).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):  # noqa: D401
        if not request.path.startswith("/api/"):
            return None

        error_logger.exception(
            "Unhandled API exception on %s %s rid=%s",
            request.method,
            request.path,
            getattr(request, "request_id", "-"),
        )
        message = "An unexpected server error occurred."
        if settings.DEBUG:
            message = f"{type(exception).__name__}: {exception}"
        return JsonResponse(
            {
                "error": {
                    "code": "server_error",
                    "message": message,
                    "status": 500,
                    "request_id": getattr(request, "request_id", None),
                }
            },
            status=500,
        )


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "-")
