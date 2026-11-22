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
