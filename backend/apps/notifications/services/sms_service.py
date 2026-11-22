"""SMS delivery through 2Factor.

2Factor accepts a six-digit OTP and sends its own templated message. That means
the authentication layer keeps ownership of code generation and verification,
and 2Factor is purely transport - which is what makes the provider swappable.

API shape used (v1):
    GET {base}/{API_KEY}/SMS/{mobile}/{otp}
    GET {base}/{API_KEY}/SMS/{mobile}/AUTOGEN   # provider-generated code

We always use the first form: the code must come from our own secure generator
so it can be hashed and verified by the shared OTP service.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger("apps.notifications.sms")


class SMSDeliveryError(Exception):
    """Raised when the SMS provider rejects or cannot be reached."""


def _digits_only(mobile_number: str) -> str:
    """2Factor wants 10 digits for India (or full E.164 without '+')."""
    return "".join(ch for ch in mobile_number if ch.isdigit())


def send_otp_sms(*, mobile_number: str, code: str) -> bool:
    """Deliver an OTP by SMS. Returns True on success.

    With no API key configured this raises, so the caller surfaces a clear
    configuration error instead of pretending a message went out.
    """
    if not settings.TWOFACTOR_API_KEY:
        raise SMSDeliveryError(
            "TWOFACTOR_API_KEY is not configured. Add it to .env to send real SMS."
        )

    number = _digits_only(mobile_number)
    # Drop the 91 country code: 2Factor expects the 10-digit national number.
    if len(number) == 12 and number.startswith("91"):
        number = number[2:]

    url = f"{settings.TWOFACTOR_BASE_URL.rstrip('/')}/{settings.TWOFACTOR_API_KEY}/SMS/{number}/{code}"

    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        logger.warning("2Factor request failed: %s", type(exc).__name__)
        raise SMSDeliveryError("Could not reach the SMS provider.") from exc

    if response.status_code != 200:
        logger.warning("2Factor rejected the message (status %s)", response.status_code)
        raise SMSDeliveryError("The SMS provider rejected the message.")

    # 2Factor answers 200 with {"Status": "Success", ...}
    try:
        payload = response.json()
    except ValueError:
        raise SMSDeliveryError("The SMS provider returned an unreadable response.")

    if str(payload.get("Status", "")).lower() != "success":
        logger.warning("2Factor returned a non-success status")
        raise SMSDeliveryError("The SMS provider could not send this message.")

    logger.info("OTP SMS accepted by 2Factor")
    return True
