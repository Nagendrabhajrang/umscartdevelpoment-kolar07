"""Request identity resolution for customer-scoped endpoints.

Order of precedence:

1. **A JWT-authenticated request.** When the caller presents a valid access
   token, the acting customer is that account's linked ``Customer`` row. This is
   the real path and the only one that is a security boundary.
2. The ``X-Customer-Id`` header, the ``customer`` query parameter, or a
   ``customer`` key in the JSON body.

The header fallback is the original development seam. It is retained because the
commerce endpoints have not yet been switched over to require authentication,
and disabling it now would break every existing client. It is *not* a security
boundary: a caller who supplies no token is still trusted to name a customer.

Migrating a view off the seam is one line: give it ``permission_classes`` that
require authentication, and :func:`resolve_customer` will then always take
branch 1.
"""

from django.conf import settings

from common.exceptions import BusinessRuleError

CUSTOMER_NOT_FOUND = "customer_not_found"
CUSTOMER_REQUIRED = "customer_context_required"


def get_customer_id(request):
    """Return the raw customer id supplied by the client, or ``None``."""
    header_name = getattr(settings, "CUSTOMER_ID_HEADER", "X-Customer-Id")
    meta_key = "HTTP_" + header_name.upper().replace("-", "_")

    raw = request.META.get(meta_key)
    if raw in (None, ""):
        raw = request.query_params.get(
            getattr(settings, "CUSTOMER_ID_QUERY_PARAM", "customer")
        )
    if raw in (None, "") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        data = getattr(request, "data", None)
        if isinstance(data, dict):
            raw = data.get("customer") or data.get("customer_id")
    return raw


def _customer_from_token(request):
    """Return the ``Customer`` linked to an authenticated user, or ``None``.

    Only customer-role accounts are considered: an authenticated admin has no
    commerce identity, and must not silently act as somebody's customer.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "role", None) != "CUSTOMER":
        return None

    from apps.customers.selectors import get_customer_by_id

    link = getattr(user, "customer_profile", None)
    if link is None:
        return None
    return get_customer_by_id(link.customer_id)


def _token_was_presented(request) -> bool:
    """True when the caller sent an Authorization header at all.

    Used only to keep error reporting honest: a request carrying a bearer token
    is an authenticated request, so an optional customer lookup must resolve to
    ``None`` rather than raise the "no identity supplied" error.
    """
    header = request.META.get("HTTP_AUTHORIZATION", "")
    return bool(header.strip())


def _repair_customer_link(user):
    """Re-create the ``CustomerProfile`` link for a signed-in customer.

    Idempotent and safe to call on every request: it only runs when the link is
    genuinely missing. Returns the ``Customer`` row, or ``None`` when one cannot
    be built (for example the mobile number is no longer valid).
    """
    try:
        from apps.authentication.services.auth_service import _ensure_customer_profile

        profile = _ensure_customer_profile(user)
        return getattr(profile, "customer", None)
    except Exception:  # pragma: no cover - never fail a request over a repair
        return None


def resolve_customer(request, required: bool = True):
    """Return the :class:`~apps.customers.models.Customer` acting for this request.

    A valid access token wins over any header, so a signed-in shopper can never
    be redirected to another account by editing a request header.

    Raises:
        BusinessRuleError: when ``required`` is true and no (valid) customer id
            was supplied, or when an authenticated customer has no linked
            commerce profile (a server-side fault, reported as such).
    """
    from apps.customers.selectors import get_customer_by_id

    authenticated_customer = _customer_from_token(request)
    if authenticated_customer is not None:
        if not authenticated_customer.can_order:
            raise BusinessRuleError(
                message="This customer account is not active.",
                code="customer_inactive",
                details={
                    "customer_id": authenticated_customer.id,
                    "status": authenticated_customer.status,
                },
            )
        return authenticated_customer

    # An authenticated customer with no linked Customer row is OUR bug, not the
    # shopper's fault - so repair it here instead of failing the request.
    #
    # Before round 24 this raised 409 `customer_profile_missing`, which the
    # storefront treated as an expired session: the shopper was signed out
    # within a second of signing in, every time, with no way to recover. The
    # link is derivable from the mobile number, so the server can simply
    # recreate it and carry on.
    user = getattr(request, "user", None)
    if (
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "role", None) == "CUSTOMER"
        and _customer_from_token(request) is None
    ):
        repaired = _repair_customer_link(user)
        if repaired is not None and repaired.can_order:
            return repaired
        raise BusinessRuleError(
            message=(
                "We could not open your customer account. Please try again; if "
                "this continues, contact support."
            ),
            code="customer_profile_missing",
            status_code=409,
        )

    # A caller who presented a token is NOT anonymous, even when that token
    # could not be resolved. Returning "no customer" here (instead of the
    # "supply a header" error) keeps an optional lookup from looking like a
    # missing identity - the request is authenticated, just not mapped.
    if _token_was_presented(request):
        return None

    raw = get_customer_id(request)
    if raw in (None, ""):
        if required:
            raise BusinessRuleError(
                # Shopper-facing text only. The header name was never something
                # a customer could act on, and printing it was the exact
                # complaint in round 22.
                message="Please sign in to continue.",
                code=CUSTOMER_REQUIRED,
                details={
                    "header": getattr(settings, "CUSTOMER_ID_HEADER", "X-Customer-Id"),
                    "hint": "sign_in_required",
                },
            )
        return None

    customer = get_customer_by_id(raw)
    if customer is None:
        # The id came from the legacy header, not from a token. A browser that
        # still holds an id from an earlier demo session must not be met with a
        # hard error on an anonymous request: it is not a security boundary, and
        # the shopper cannot fix a stale localStorage value themselves.
        #
        # Required endpoints (cart, checkout) still refuse, but with a message
        # that says what to do. Optional ones resolve to "no customer".
        if not required:
            return None
        # 404 is the correct status for a customer that does not exist; the
        # message and `hint` do the explaining, since the caller cannot fix a
        # stale id in their browser storage themselves.
        raise BusinessRuleError(
            message=(
                f"Customer '{raw}' does not exist. "
                "Please sign in again to continue."
            ),
            code=CUSTOMER_NOT_FOUND,
            details={"customer": str(raw), "hint": "sign_in_required"},
            status_code=404,
        )
    if not customer.can_order:
        raise BusinessRuleError(
            message="This customer account is not active.",
            code="customer_inactive",
            details={"customer_id": customer.id, "status": customer.status},
        )
    return customer
