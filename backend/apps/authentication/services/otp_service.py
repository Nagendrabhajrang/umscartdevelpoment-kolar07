"""Reusable OTP service.

One service serves both the admin email OTP and the customer mobile OTP. The
delivery channel is the only thing that varies, so swapping SMS or email
providers never touches this logic.

Guarantees
----------
* Six digits from a cryptographically secure RNG (``secrets``).
* Stored only as a Django password hash - never plaintext, never logged.
* Five-minute expiry, five verification attempts, sixty-second resend cooldown.
* A verified OTP can never be used twice; a superseded OTP is dead immediately.
* Account-scoped and IP-scoped rate limits, both persisted in the database.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.authentication.models import (
    DeliveryChannel,
    OTPThrottle,
    OTPVerification,
    OTPPurpose,
)
from common.exceptions import BusinessRuleError, ValidationError
from config.settings.base import dev_mode_active


def mask_mobile(number: str) -> str:
    """+919876543210 -> +9198XXXX3210 (safe to return to a client)."""
    if not number:
        return ""
    digits = number.lstrip("+")
    if len(digits) <= 6:
        return "*" * len(digits)
    return f"+{digits[:4]}{'X' * (len(digits) - 8)}{digits[-4:]}"


def mask_email(email: str) -> str:
    """nagendrajoe@gmail.com -> nag*******@gmail.com"""
    if not email or "@" not in email:
        return email or ""
    local, _, domain = email.partition("@")
    keep = local[:3]
    return f"{keep}{'*' * max(len(local) - 3, 1)}@{domain}"


def _generate_code() -> str:
    """A uniformly random N-digit code with no modulo bias.

    ``secrets.randbelow`` is rejection-sampled internally, so every code is
    equally likely - ``random.randint`` would not be acceptable here.
    """
    length = settings.OTP_LENGTH
    upper = 10 ** length
    return str(secrets.randbelow(upper)).zfill(length)


def _consume_throttle(scope: str, key: str, limit: int, window_seconds: int = 3600):
    """Increment a fixed-window counter, raising once the limit is passed."""
    now = timezone.now()
    window_start = now - timedelta(seconds=window_seconds)
    with transaction.atomic():
        row = (
            OTPThrottle.objects.select_for_update()
            .filter(scope=scope, key=key, window_start__gte=window_start)
            .order_by("-window_start")
            .first()
        )
        if row is None:
            row = OTPThrottle.objects.create(
                scope=scope, key=key, window_start=now, count=0
            )
        row.count += 1
        row.save(update_fields=["count"])
        if row.count > limit:
            raise BusinessRuleError(
                message="Too many verification requests. Please try again later.",
                code="otp_rate_limited",
            )


def issue_otp(
    *,
    user,
    purpose: str,
    channel: str,
    destination: str = "",
    ip_address: str | None = None,
) -> tuple[OTPVerification, str | None]:
    """Create and deliver a fresh OTP.

    Returns ``(record, code)``.

    ``code`` is the plaintext, and it exists in memory *only* so the caller can
    hand it to a delivery provider - the database keeps the hash and nothing
    else. Callers must never log it. Whether it is echoed back to a client is a
    separate decision made by the view layer, gated on ``AUTH_DEV_MODE``.
    """
    now = timezone.now()

    # --- resend cooldown (per user + purpose) -----------------------------
    cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS
    latest = (
        OTPVerification.objects.filter(user=user, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if latest and (now - latest.created_at).total_seconds() < cooldown:
        wait = int(cooldown - (now - latest.created_at).total_seconds())
        raise BusinessRuleError(
            message=f"Please wait {wait} seconds before requesting another code.",
            code="otp_resend_cooldown",
            details={"retry_after_seconds": wait},
        )

    # --- rate limits ------------------------------------------------------
    _consume_throttle(
        "otp_user", f"{user.pk}:{purpose}", settings.OTP_MAX_REQUESTS_PER_HOUR
    )
    if ip_address:
        _consume_throttle(
            "otp_ip", str(ip_address), settings.OTP_MAX_REQUESTS_PER_IP_PER_HOUR
        )

    code = _generate_code()
    expiry = now + timedelta(seconds=settings.OTP_VALIDITY_SECONDS)

    with transaction.atomic():
        # Supersede any live code for this purpose: only the newest one works.
        OTPVerification.objects.filter(
            user=user, purpose=purpose, is_verified=False
        ).update(expires_at=now)

        record = OTPVerification.objects.create(
            user=user,
            otp_hash=make_password(code),
            purpose=purpose,
            delivery_channel=channel,
            destination=destination,
            expires_at=expiry,
            max_attempts=settings.OTP_MAX_ATTEMPTS,
        )

    return record, code


def verify_otp(*, user, purpose: str, code: str) -> OTPVerification:
    """Validate a submitted code and consume it.

    Raises ``ValidationError`` with a specific code for each failure mode so the
    client can tell "wrong digits" from "expired" from "too many attempts".
    """
    record = (
        OTPVerification.objects.filter(user=user, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if record is None:
        raise ValidationError(message="Request a code first.", code="otp_not_requested")

    if record.is_verified:
        raise ValidationError(
            message="This code has already been used. Request a new one.",
            code="otp_already_used",
        )

    if record.is_expired:
        raise ValidationError(
            message="This code has expired. Request a new one.", code="otp_expired"
        )

    if record.is_exhausted:
        raise ValidationError(
            message="Too many incorrect attempts. Request a new code.",
            code="otp_attempts_exhausted",
        )

    if not check_password(code, record.otp_hash):
        # Count the failure atomically so parallel guesses cannot slip past.
        OTPVerification.objects.filter(pk=record.pk).update(attempts=models_f())
        record.refresh_from_db()
        remaining = max(record.max_attempts - record.attempts, 0)
        raise ValidationError(
            message="That code is not correct.",
            code="otp_invalid",
            details={"attempts_remaining": remaining},
        )

    # Correct: burn it immediately so it can never be replayed.
    record.is_verified = True
    record.save(update_fields=["is_verified"])
    return record


def models_f():
    """Small helper so the F-expression import stays local and obvious."""
    from django.db.models import F

    return F("attempts") + 1


def otp_destination_for(user, channel: str) -> str:
    if channel == DeliveryChannel.EMAIL:
        return user.email or ""
    return user.mobile_number or ""
