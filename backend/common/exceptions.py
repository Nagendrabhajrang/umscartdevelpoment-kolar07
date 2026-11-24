"""Domain exceptions and the global DRF exception handler.

Service-layer code raises :class:`BusinessRuleError` (or a subclass) instead of
DRF exceptions so that business logic stays framework agnostic. The handler
below converts them into a single, predictable error envelope:

    {
        "error": {
            "code": "insufficient_stock",
            "message": "Only 3 unit(s) of 'Basmati Rice 5kg' are available.",
            "details": {...}          # optional
        }
    }
"""

import logging
import re
import uuid

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, Throttled
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.views import exception_handler

logger = logging.getLogger("common.exceptions")

ERROR_CODE_FOR_STATUS = {
    400: "bad_request",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    409: "conflict",
    415: "unsupported_media_type",
    422: "unprocessable_entity",
    429: "throttled",
    500: "server_error",
}


class BusinessRuleError(APIException):
    """A violated business rule. Rendered as HTTP 400 by default."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This operation violates a business rule."
    default_code = "business_rule_violation"

    def __init__(self, message=None, code=None, details=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        self.code = code or self.default_code
        self.details = details
        super().__init__(message or self.default_detail, self.code)


class ValidationError(BusinessRuleError):
    """A rejected input value. Same envelope as the rest of the API."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This value is not valid."
    default_code = "invalid"


class AuthenticationRequiredError(BusinessRuleError):
    """No usable credentials were supplied."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Please sign in to continue."
    default_code = "not_authenticated"


class SessionExpiredError(AuthenticationRequiredError):
    """The session behind these tokens is gone (logged out elsewhere)."""

    default_detail = "Your session has ended. Please sign in again."
    default_code = "session_expired"


class ResourceNotFoundError(BusinessRuleError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "The requested resource does not exist."
    default_code = "not_found"


class ConflictError(BusinessRuleError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state of the resource."
    default_code = "conflict"


class InsufficientStockError(BusinessRuleError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Insufficient stock for one or more products."
    default_code = "insufficient_stock"


class EmptyResourceError(BusinessRuleError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The requested operation requires at least one item."
    default_code = "empty_resource"


class PaymentRequiredError(BusinessRuleError):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Payment could not be verified."
    default_code = "payment_required"


def _normalise_details(detail):
    """Flatten DRF's ErrorDetail objects into plain JSON-serialisable data."""
    if isinstance(detail, dict):
        return {key: _normalise_details(value) for key, value in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [_normalise_details(item) for item in detail]
    return str(detail)


def _first_message(detail) -> str:
    if isinstance(detail, dict):
        for key, value in detail.items():
            message = _first_message(value)
            if message:
                return f"{key}: {message}" if key != "detail" else message
        return "Validation failed."
    if isinstance(detail, (list, tuple)):
        return _first_message(detail[0]) if detail else "Validation failed."
    return str(detail)


def _envelope(code, message, details=None, status_code=400):
    payload = {"error": {"code": code, "message": message}}
    if details not in (None, {}, []):
        payload["error"]["details"] = details
    payload["error"]["status"] = status_code
    return payload


def ums_mart_exception_handler(exc, context):
    """Convert every exception into the UMS Mart error envelope."""

    # --- Domain exceptions -------------------------------------------------
    if isinstance(exc, BusinessRuleError):
        payload = _envelope(exc.code, str(getattr(exc, "detail", exc)), exc.details, exc.status_code)
        return _response(payload, exc.status_code)

    # --- Django-level exceptions -------------------------------------------
    if isinstance(exc, DjangoValidationError):
        details = exc.message_dict if hasattr(exc, "message_dict") else {"non_field_errors": exc.messages}
        payload = _envelope("validation_error", _first_message(details), details)
        return _response(payload, status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, Http404) or isinstance(exc, ObjectDoesNotExist):
        payload = _envelope("not_found", "The requested resource does not exist.")
        return _response(payload, status.HTTP_404_NOT_FOUND)

    if isinstance(exc, IntegrityError):
        logger.warning("IntegrityError handled: %s", exc, exc_info=False)
        payload = _envelope(
            "integrity_error",
            "The record could not be saved because it would violate a database constraint.",
        )
        return _response(payload, status.HTTP_409_CONFLICT)

    # --- DRF exceptions ----------------------------------------------------
    response = exception_handler(exc, context)
    if response is None:
        # Unhandled exception -> let Django's 500 handling and logging run.
        logger.exception("Unhandled exception in %s", context.get("view"), exc_info=exc)
        return None

    detail = response.data
    status_code = response.status_code
    # Filled in only where a more precise explanation exists (currently the CSRF
    # branch); every other case keeps the historical empty `details`.
    details = None

    if isinstance(exc, DRFValidationError):
        code = "validation_error"
        message = _first_message(detail)
    elif isinstance(exc, Throttled):
        code = "throttled"
        message = f"Request was throttled. Try again in {int(exc.wait or 0)} seconds."
    elif isinstance(exc, PermissionDenied):
        code = "permission_denied"
        # Round 37: a CSRF failure and a genuine role denial both arrive here as
        # PermissionDenied, and collapsing them into one sentence produced the
        # worst possible error message: a signed-in admin changing a category was
        # told they "do not have permission", when the real problem was a stale
        # CSRF token that a hard refresh fixes. Name the actual cause.
        csrf_detail = ""
        if isinstance(detail, dict):
            csrf_detail = str(detail.get("detail") or "")
        elif isinstance(detail, (list, tuple)) and detail:
            csrf_detail = str(detail[0])
        elif isinstance(detail, str):
            # DRF's own CSRF guard sends {"detail": ...}, but a bare string reaches
            # here from other call sites - treat it the same instead of decaying
            # into a generic "no permission" message.
            csrf_detail = str(detail)
        if "CSRF" in csrf_detail.upper():
            code = "csrf_failed"
            # Round 38: one sentence covered three very different failures, so a
            # misconfigured host sent people refreshing the page forever. DRF puts
            # the real cause in the detail text - surface it.
            lowered = csrf_detail.lower()
            if "origin" in lowered:
                csrf_reason = "origin_mismatch"
                # DRF says which origin it rejected: "Origin checking failed -
                # http://localhost:5175 does not match any trusted origins."
                # Naming it (and the list we do trust) turns a guessing game into
                # a one-line fix, especially when a dev server lands on a port
                # nobody expected.
                match = re.search(r"https?://[^\s'\"()]+", csrf_detail)
                origin = match.group(0).rstrip(".,)") if match else ""
                trusted = list(getattr(settings, "CSRF_TRUSTED_ORIGINS", []) or [])
                where = f" ({origin})" if origin else ""
                message = (
                    f"This page's address{where} is not in the API's list of "
                    "trusted origins, so the change was rejected. Add it to "
                    "CSRF_TRUSTED_ORIGINS in backend/.env and restart the API."
                )
                if trusted:
                    shown = ", ".join(trusted[:6])
                    if len(trusted) > 6:
                        shown += f", ... ({len(trusted)} total)"
                    message += f" Trusted right now: {shown}."
                details = {
                    "reason": csrf_reason,
                    "origin": origin,
                    "trusted_origins": trusted,
                }
            elif "incorrect" in lowered or "mismatch" in lowered:
                csrf_reason = "token_mismatch"
                message = (
                    "Your security token was out of date, so the change was not "
                    "saved. It has been refreshed - please try that once more."
                )
            elif "referer" in lowered:
                csrf_reason = "referer_missing"
                message = (
                    "This browser hid the address the change came from (no "
                    "Referer header), so the API could not verify the request. "
                    "Turn off strict referrer blocking for this site, or open the "
                    "store over http://localhost instead of a LAN IP or HTTPS tunnel."
                )
            elif "not set" in lowered or "missing" in lowered or "no csrf" in lowered:
                csrf_reason = "token_missing"
                message = (
                    "This browser did not send the security cookie the change "
                    "needs. Allow cookies for this site, then try again."
                )
            else:
                csrf_reason = "rejected"
                message = (
                    "Your security token could not be verified, so this change "
                    "was not saved. The server said: "
                    f"{csrf_detail[:160]}"
                )
            details = {
                **(details or {}),
                "reason": csrf_reason,
                "server_detail": csrf_detail[:200],
            }
        else:
            message = "You do not have permission to perform this action."
    else:
        error_detail = detail.get("detail", detail) if isinstance(detail, dict) else detail
        code = ERROR_CODE_FOR_STATUS.get(status_code, "error")
        message = _first_message(error_detail)

    # Preserve the original DRF shape inside "details" for field level errors.
    # The CSRF branch above may already have filled it in with its reason.
    if isinstance(exc, DRFValidationError):
        details = detail
    elif not isinstance(details, dict):
        details = None
    response.data = _envelope(code, message, details, status_code)
    return response


def _response(payload, status_code):
    from rest_framework.response import Response

    return Response(payload, status=status_code)


class RequestIDMissing(Exception):
    """Raised internally when a correlation id cannot be resolved."""


def new_request_id() -> str:
    return uuid.uuid4().hex
