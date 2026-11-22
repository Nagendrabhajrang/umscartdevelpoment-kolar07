"""Email delivery.

Provider is chosen at runtime from configuration, so the authentication flow is
unchanged whether mail goes through Resend, a console fallback, or (in
production) the configured SMTP relay.

Order of preference:
1. Resend  - when ``RESEND_API_KEY`` is set.
2. SMTP    - when ``EMAIL_HOST`` is set and configured.
3. Console - development fallback; writes the rendered message to
             ``core.mail.outbox``-style logging *and* a gitignored outbox file.

The OTP itself is never written to the application log by any branch.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger("apps.notifications.email")

# Development-only file so a developer can read the last message without
# digging through a provider dashboard. Gitignored; never used in production.
DEV_OUTBOX = Path(settings.BASE_DIR) / "logs" / "dev_outbox.txt"


class EmailDeliveryError(Exception):
    """Raised when every configured channel fails."""


def _send_via_resend(subject: str, text: str, html: str, to: str) -> bool:
    payload = {
        "from": settings.RESEND_FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "text": text,
        "html": html,
    }
    try:
        response = requests.post(
            settings.RESEND_API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
    except requests.RequestException as exc:  # network down, DNS, timeout
        logger.warning("Resend request failed: %s", type(exc).__name__)
        return False

    if response.status_code in (200, 201):
        logger.info("OTP email accepted by Resend (status %s)", response.status_code)
        return True

    # Log the status only - never the body, which can echo the payload.
    logger.warning("Resend rejected the message (status %s)", response.status_code)
    return False


def _send_via_smtp(subject: str, text: str, html: str, to: str) -> bool:
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        if html:
            message.attach_alternative(html, "text/html")
        message.send(fail_silently=False)
        logger.info("OTP email sent over SMTP")
        return True
    except Exception as exc:  # noqa: BLE001 - provider errors vary widely
        logger.warning("SMTP send failed: %s", type(exc).__name__)
        return False


def _smtp_is_real() -> bool:
    """True only when Django is configured to talk to a real mail server.

    The console and locmem backends are development conveniences: they accept
    every message and deliver nothing, so a successful ``send()`` from them must
    never be reported to a caller as delivery.
    """
    backend = getattr(settings, "EMAIL_BACKEND", "") or ""
    if "smtp" not in backend.lower():
        return False
    host = getattr(settings, "EMAIL_HOST", "") or ""
    return bool(host) and host != "localhost"


def _write_dev_outbox(subject: str, text: str, to: str) -> None:
    """Development fallback: persist the message locally, no secrets in logs."""
    try:
        DEV_OUTBOX.parent.mkdir(parents=True, exist_ok=True)
        with DEV_OUTBOX.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\n{'=' * 70}\nTo: {to}\nSubject: {subject}\n{'-' * 70}\n{text}\n"
            )
        logger.info("OTP email written to the development outbox (no provider configured)")
    except OSError:
        logger.warning("Could not write the development outbox")


def send_email(*, to: str, subject: str, template: str, context: dict) -> bool:
    """Render a template and deliver it through the best available channel."""
    if not to:
        raise EmailDeliveryError("No recipient address.")

    text = render_to_string(f"notifications/email/{template}.txt", context)
    try:
        html = render_to_string(f"notifications/email/{template}.html", context)
    except Exception:  # template optional - text version is enough
        html = ""

    if settings.RESEND_API_KEY and _send_via_resend(subject, text, html, to):
        return True

    # Only treat SMTP as a delivery channel when the backend actually sends mail.
    # Django defaults EMAIL_HOST to "localhost", so checking the host alone made
    # this branch fire under the *console* backend: message.send() wrote to
    # stdout, returned 1, and the login response claimed an email had been sent.
    if _smtp_is_real() and _send_via_smtp(subject, text, html, to):
        return True

    if settings.EMAIL_CONSOLE_FALLBACK and settings.DEBUG:
        # Written to a local file, NOT delivered. Returning True here made the
        # login response claim "a code has been sent" when nothing left the
        # machine, which is exactly the kind of lie that wastes debugging time.
        _write_dev_outbox(subject, text, to)
        return False

    raise EmailDeliveryError("No email channel is configured and delivery failed.")


def send_otp_email(*, to: str, code: str, purpose_label: str, minutes: int) -> bool:
    """The one call authentication code makes; wording lives in the template."""
    return send_email(
        to=to,
        # Never put the code in the subject: subject lines travel in provider
        # logs, notification previews and mail-client telemetry in clear text.
        subject=f"UMS Mart verification code ({purpose_label})",
        template="otp",
        context={
            "code": code,
            "purpose_label": purpose_label,
            "validity_minutes": minutes,
            "store_name": "UMS Mart",
        },
    )
