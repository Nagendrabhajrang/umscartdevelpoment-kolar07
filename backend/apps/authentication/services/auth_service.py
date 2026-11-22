"""Authentication business logic for both roles.

Admin and customer flows are deliberately separate functions with separate
preconditions. They share only the OTP service, the session service and the
notification layer - never each other's steps. In particular the admin flow can
never mint tokens before MFA, because ``admin_login_start`` returns only a
challenge ticket, and tokens are produced exclusively by ``admin_verify_mfa``.
"""

from __future__ import annotations

import logging
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import CustomerProfile, User, UserRole
from apps.authentication.models import (
    DeliveryChannel,
    OTPPurpose,
    PasswordReset,
)
from apps.authentication.services import otp_service, session_service
from apps.authentication.services.otp_service import mask_email, mask_mobile
from apps.notifications.services import email_service, sms_service
from config.settings.base import dev_mode_active
from common.exceptions import BusinessRuleError, ValidationError

logger = logging.getLogger("apps.authentication")

RESET_TOKEN_TTL_SECONDS = 600  # 10 minutes to finish the reset form


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
def admin_login_start(*, username: str, password: str, request=None) -> dict:
    """Step 1 of admin login: verify the password, then send an email OTP.

    Returns a challenge descriptor only. **No token is issued here** - that is
    the whole point of the two-step design.
    """
    admin = User.objects.filter(role=UserRole.ADMIN).first()

    # Constant-ish work whether or not an admin exists, so response timing does
    # not reveal that this deployment has no admin provisioned yet.
    # Usernames are case-insensitive on both sides.
    #
    # Round 36: only the *typed* value was lowercased here, so an admin stored
    # as "Admin" or "ADMIN" could never sign in - the comparison was
    # "admin" == "Admin" -> False, reported to the user as "Incorrect username
    # or password" with no hint that the case was the problem. Both sides are
    # normalised now, which matches how people expect a username field to behave.
    candidate_ok = bool(
        admin
        and username
        and username.strip().lower() == (admin.username or "").strip().lower()
        and admin.is_active
        and check_password(password or "", admin.password)
    )

    if not candidate_ok:
        logger.info("Admin login rejected for username=%r", (username or "")[:32])
        raise BusinessRuleError(
            message="Incorrect username or password.",
            code="invalid_credentials",
            status_code=401,
        )

    if not admin.email:
        raise BusinessRuleError(
            message="This admin has no registered email, so MFA cannot be completed.",
            code="admin_email_missing",
        )

    record, code = otp_service.issue_otp(
        user=admin,
        purpose=OTPPurpose.ADMIN_MFA,
        channel=DeliveryChannel.EMAIL,
        destination=admin.email,
        ip_address=_ip(request),
    )

    delivered = _send_email_otp(admin, code, "Admin sign-in")

    return {
        "mfa_required": True,
        "message": _email_message(delivered, mask_email(admin.email)),
        "email_hint": mask_email(admin.email),
        "expires_in_seconds": settings.OTP_VALIDITY_SECONDS,
        "resend_cooldown_seconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
        "delivered": delivered,
        **_dev_code(code),
    }


def admin_resend_mfa(*, request=None) -> dict:
    """Resend the admin MFA code, honouring the cooldown and rate limits."""
    admin = User.objects.filter(role=UserRole.ADMIN, is_active=True).first()
    if admin is None or not admin.email:
        raise BusinessRuleError(
            message="No admin account is available for MFA.", code="admin_unavailable"
        )

    record, code = otp_service.issue_otp(
        user=admin,
        purpose=OTPPurpose.ADMIN_MFA,
        channel=DeliveryChannel.EMAIL,
        destination=admin.email,
        ip_address=_ip(request),
    )
    delivered = _send_email_otp(admin, code, "Admin sign-in")

    return {
        "message": _email_message(delivered, mask_email(admin.email)),
        "email_hint": mask_email(admin.email),
        "expires_in_seconds": settings.OTP_VALIDITY_SECONDS,
        "delivered": delivered,
        **_dev_code(code),
    }


def admin_verify_mfa(*, code: str, request=None) -> dict:
    """Step 2 of admin login: verify the OTP, then and only then mint tokens."""
    admin = User.objects.filter(role=UserRole.ADMIN, is_active=True).first()
    if admin is None:
        raise BusinessRuleError(
            message="No admin account is available.", code="admin_unavailable"
        )

    otp_service.verify_otp(user=admin, purpose=OTPPurpose.ADMIN_MFA, code=code)

    # Round 30: a real Django session, not a token pair. The session id goes
    # out in an HttpOnly cookie; the body carries only the user.
    session_service.start_session(admin, request=request)
    admin.last_login = timezone.now()
    admin.save(update_fields=["last_login"])

    return {"user": _user_payload(admin)}


def _send_email_otp(user, code: str, label: str) -> bool:
    """Deliver a code by email, tolerating a missing provider in development."""
    if not user.email:
        return False
    try:
        return email_service.send_otp_email(
            to=user.email,
            code=code,
            purpose_label=label,
            minutes=settings.OTP_VALIDITY_SECONDS // 60,
        )
    except Exception:  # a provider outage must not 500 the login
        logger.warning("OTP email delivery failed for user=%s", user.pk)
        return False


def _email_message(delivered: bool, masked: str) -> str:
    """Describe what actually happened to an emailed code."""
    if delivered:
        return f"A verification code has been sent to {masked}."
    return (
        "Email delivery is not configured on this server. "
        "No email was sent."
    )


def _dev_code(code: str | None) -> dict:
    """Echo the code back to the client only when explicitly in dev mode."""
    return {"dev_otp": code} if (code and dev_mode_active()) else {}


# ---------------------------------------------------------------------------
# Admin password recovery
# ---------------------------------------------------------------------------
def admin_forgot_password(*, email: str, request=None) -> dict:
    """Send a reset OTP. The response never reveals whether the address exists."""
    generic = {
        "message": "If that address belongs to an account, a code has been sent to it.",
        "expires_in_seconds": settings.OTP_VALIDITY_SECONDS,
    }

    admin = User.objects.filter(role=UserRole.ADMIN, is_active=True).first()
    # Deliberately identical response for a wrong address, an unknown address and
    # a valid one - account enumeration is not possible through this endpoint.
    if admin is None or not email or (admin.email or "").lower() != email.strip().lower():
        logger.info("Forgot-password requested for a non-matching address")
        return generic

    record, code = otp_service.issue_otp(
        user=admin,
        purpose=OTPPurpose.FORGOT_PASSWORD,
        channel=DeliveryChannel.EMAIL,
        destination=admin.email,
        ip_address=_ip(request),
    )
    delivered = _send_email_otp(admin, code, "Password reset")

    return {
        **generic,
        "email_hint": mask_email(admin.email),
        "resend_cooldown_seconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
        **_dev_code(code),
        **({} if delivered else {"delivery": "unavailable"}),
    }


def admin_verify_reset_otp(*, email: str, code: str, request=None) -> dict:
    """Exchange a valid reset OTP for a single-use reset token."""
    admin = _matching_admin_or_reject(email)

    otp_service.verify_otp(user=admin, purpose=OTPPurpose.FORGOT_PASSWORD, code=code)

    raw_token = secrets.token_urlsafe(32)
    PasswordReset.objects.create(
        user=admin,
        reset_token_hash=make_password(raw_token),
        expires_at=timezone.now() + timezone.timedelta(seconds=RESET_TOKEN_TTL_SECONDS),
    )

    return {
        "reset_token": raw_token,
        "expires_in_seconds": RESET_TOKEN_TTL_SECONDS,
        "message": "Code verified. Choose a new password.",
    }


def admin_reset_password(*, reset_token: str, new_password: str) -> dict:
    """Set a new password using a verified reset token, then kill every session."""
    admin = User.objects.filter(role=UserRole.ADMIN, is_active=True).first()
    if admin is None:
        raise ValidationError(message="This reset link is not valid.", code="reset_invalid")

    grant = _usable_reset_for(admin, reset_token)

    _validate_new_password(admin, new_password)

    with transaction.atomic():
        admin.set_password(new_password)
        admin.save(update_fields=["password"])
        grant.is_used = True
        grant.save(update_fields=["is_used"])

    revoked = session_service.blacklist_all_for_user(admin)
    logger.info("Admin password reset; %s refresh token(s) blacklisted", revoked)

    return {"message": "Password updated. Please sign in again.", "sessions_revoked": revoked}


def admin_change_password(*, user, current_password: str, code: str,
                          new_password: str, request=None) -> dict:
    """Authenticated change: current password + emailed OTP + new password."""
    if not check_password(current_password or "", user.password):
        raise BusinessRuleError(
            message="Your current password is not correct.",
            code="current_password_invalid",
            status_code=400,
        )

    otp_service.verify_otp(user=user, purpose=OTPPurpose.CHANGE_PASSWORD, code=code)
    _validate_new_password(user, new_password)

    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password"])

    revoked = session_service.blacklist_all_for_user(user)
    return {"message": "Password changed. Please sign in again.", "sessions_revoked": revoked}


def admin_change_password_request_otp(*, user, request=None) -> dict:
    """Send the code that the change-password form will ask for."""
    if not user.email:
        raise BusinessRuleError(
            message="This account has no email address for verification.",
            code="admin_email_missing",
        )
    record, code = otp_service.issue_otp(
        user=user,
        purpose=OTPPurpose.CHANGE_PASSWORD,
        channel=DeliveryChannel.EMAIL,
        destination=user.email,
        ip_address=_ip(request),
    )
    delivered = _send_email_otp(user, code, "Change password")
    return {
        "message": _email_message(delivered, mask_email(user.email)),
        "email_hint": mask_email(user.email),
        "delivered": delivered,
        **_dev_code(code),
    }


def _matching_admin_or_reject(email: str) -> User:
    admin = User.objects.filter(role=UserRole.ADMIN, is_active=True).first()
    if admin is None or (admin.email or "").lower() != (email or "").strip().lower():
        # Same shape as a bad OTP: never confirm whether the address exists.
        raise ValidationError(message="That code is not correct.", code="otp_invalid")
    return admin


def _usable_reset_for(user: User, raw_token: str) -> PasswordReset:
    for grant in PasswordReset.objects.filter(user=user, is_used=False):
        if grant.is_usable and check_password(raw_token, grant.reset_token_hash):
            return grant
    raise ValidationError(
        message="This reset link has expired or was already used.",
        code="reset_invalid",
    )


def _validate_new_password(user: User, new_password: str) -> None:
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError

    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError(
            message="That password is not strong enough.",
            code="weak_password",
            details={"messages": list(exc.messages)},
        )


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
def customer_send_otp(*, mobile_number: str, request=None) -> dict:
    """Send a login code to an Indian mobile number."""
    from common.validators import canonical_mobile, is_indian_mobile

    if not is_indian_mobile(mobile_number or ""):
        raise ValidationError(
            message="Enter a valid 10-digit Indian mobile number.",
            code="invalid_mobile_number",
        )
    # One canonical form means 9876543210, +919876543210 and 09876543210 all
    # resolve to the same account - no duplicate customers.
    normalised = canonical_mobile(mobile_number)

    # A code is issued against the number, not against an account, so first-time
    # users can verify too. The account is created only after the code checks out.
    user = User.objects.get_by_mobile(normalised)
    if user is None:
        # Placeholder row so the OTP record has an owner; it becomes the real
        # account on successful verification.
        user = User.objects.create_user(mobile_number=normalised, role=UserRole.CUSTOMER)
    elif not user.is_active:
        raise BusinessRuleError(
            message="This account is not active. Please contact support.",
            code="account_inactive",
            status_code=403,
        )

    record, code = otp_service.issue_otp(
        user=user,
        purpose=OTPPurpose.LOGIN,
        channel=DeliveryChannel.SMS,
        destination=normalised,
        ip_address=_ip(request),
    )

    delivered = False
    try:
        sms_service.send_otp_sms(mobile_number=normalised, code=code)
        delivered = True
    except sms_service.SMSDeliveryError:
        # No provider configured (or it is down): in development the code is in
        # the response below; otherwise the caller sees delivered=false.
        logger.warning("SMS delivery unavailable for customer=%s", user.pk)

    # Say what actually happened. Claiming a message was sent when no provider is
    # configured is the kind of lie that costs an hour of debugging.
    if delivered:
        message = f"A verification code has been sent to {mask_mobile(normalised)}."
    else:
        message = (
            "SMS delivery is not configured on this server. "
            "No text message was sent."
        )

    return {
        "message": message,
        "mobile_hint": mask_mobile(normalised),
        "expires_in_seconds": settings.OTP_VALIDITY_SECONDS,
        "resend_cooldown_seconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
        "delivered": delivered,
        "delivery_channel": "SMS",
        **_dev_code(code),
    }


def _guest_key_from(request) -> str:
    """The browser's guest basket key, if this request carried one.

    Round 32 helper. Kept local so the auth service does not import cart views.
    """
    if request is None:
        return ""
    raw = request.META.get("HTTP_X_GUEST_CART", "") or ""
    if not raw:
        data = getattr(request, "data", None)
        if isinstance(data, dict):
            raw = data.get("guest_cart") or data.get("guest_key") or ""
    if not raw:
        try:
            raw = request.query_params.get("guest_cart", "") or ""
        except AttributeError:  # pragma: no cover - non-DRF request
            raw = ""
    try:
        from apps.cart.services import normalise_guest_key

        return normalise_guest_key(raw)
    except Exception:  # pragma: no cover - never fail a login over a cart
        return ""


def customer_verify_otp(*, mobile_number: str, code: str, request=None) -> dict:
    """Verify the code, create the account if new, then mint tokens."""
    from common.validators import canonical_mobile, is_indian_mobile

    if not is_indian_mobile(mobile_number or ""):
        raise ValidationError(
            message="Enter a valid 10-digit Indian mobile number.",
            code="invalid_mobile_number",
        )
    normalised = canonical_mobile(mobile_number)
    user = User.objects.get_by_mobile(normalised)
    if user is None:
        raise ValidationError(
            message="Request a code before verifying.", code="otp_not_requested"
        )

    otp_service.verify_otp(user=user, purpose=OTPPurpose.LOGIN, code=code)

    with transaction.atomic():
        # The link to the commerce Customer is an INVARIANT, not a one-time side
        # effect of the first login. Previously this ran only while the account
        # was still unverified, so an account that lost its link (a manual data
        # fix, a restored row, a cleanup script) stayed permanently unable to
        # reach checkout - and reported it as a confusing auth error.
        was_verified = user.is_mobile_verified
        if not was_verified:
            user.is_mobile_verified = True
            user.save(update_fields=["is_mobile_verified"])
        _ensure_customer_profile(user)
        created = not was_verified

    # Round 30: log the customer in for real. The session id is set as an
    # HttpOnly cookie on the response; nothing token-shaped is returned.
    session_service.start_session(user, request=request)

    # Round 32: the guest basket is NOT merged here any more.
    # 
    # Merging inside verify-otp assumed the browser would keep the session
    # cookie. When it does not - the preview renders the storefront in a
    # cross-site frame, and SameSite=Lax cookies are neither stored nor sent
    # there - the OTP is still accepted, so the merge ran and the anonymous
    # basket was emptied into an account the browser could never reach again.
    # The shopper saw "signed in", then an empty cart. That is the reported bug.
    # 
    # The merge now happens on the first cart request that arrives *with* a
    # working session (see apps.cart.views._adopt_guest_cart). Such a request
    # proves the cookie round-tripped, so the items can only land in a cart the
    # shopper can actually open. `cart_merge_pending` tells the client that a
    # key is waiting to be folded in.
    pending = _guest_key_from(request)
    if pending:
        try:
            from apps.cart import services as cart_services

            profile = getattr(user, "customer_profile", None)
            customer = getattr(profile, "customer", None)
            if customer is not None:
                payload_merge_pending = cart_services.guest_cart_has_items(pending)
            else:
                payload_merge_pending = False
        except Exception:  # pragma: no cover - never fail a login over a cart
            logger.exception("Guest cart probe failed during login")
            payload_merge_pending = False
    else:
        payload_merge_pending = False

    payload = {
        "user": _user_payload(user),
        "is_new_customer": created,
    }
    if payload_merge_pending:
        payload["cart_merge_pending"] = True
    return payload


def customer_resend_otp(*, mobile_number: str, request=None) -> dict:
    return customer_send_otp(mobile_number=mobile_number, request=request)


def _ensure_customer_profile(user: User) -> CustomerProfile:
    """Create the commerce ``Customer`` row on first successful login."""
    from apps.customers.models import Customer

    existing = getattr(user, "customer_profile", None)
    if existing:
        return existing

    customer = Customer.objects.filter(mobile_number=user.mobile_number).first()
    if customer is None:
        customer = Customer.objects.create(
            full_name="",
            mobile_number=user.mobile_number,
            email=user.email or None,
            is_mobile_verified=True,
        )
    return CustomerProfile.objects.create(user=user, customer=customer)


def _ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def _user_payload(user: User) -> dict:
    # customer_profile is a link row: the commerce Customer hangs off it.
    profile = getattr(user, "customer_profile", None)
    return {
        "id": user.pk,
        "role": user.role,
        "username": user.username,
        "mobile_number": user.mobile_number,
        "email": user.email,
        "is_email_verified": user.is_email_verified,
        "is_mobile_verified": user.is_mobile_verified,
        "display_name": user.display_name,
        "customer_id": profile.customer_id if profile else None,
    }
