"""Report whether OTP delivery is actually configured.

Answers the only question that matters when a code does not arrive: *is anything
being sent, and if not, why?* Costs nothing and sends nothing.

    python manage.py check_delivery
    python manage.py check_delivery --send-to 9876543210
    python manage.py check_delivery --send-email-to you@gmail.com
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.notifications.services import email_service, sms_service


class Command(BaseCommand):
    help = "Show which OTP channels are configured, and optionally test them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--send-to",
            metavar="MOBILE",
            help="Actually send a test SMS to this number (uses one credit).",
        )
        parser.add_argument(
            "--send-email-to",
            metavar="EMAIL",
            help="Actually send a test email to this address.",
        )

    def handle(self, *args, **options):
        sms_key = getattr(settings, "TWOFACTOR_API_KEY", "") or ""
        resend_key = getattr(settings, "RESEND_API_KEY", "") or ""
        email_host = getattr(settings, "EMAIL_HOST", "") or ""
        debug = bool(settings.DEBUG)
        dev_mode = bool(getattr(settings, "AUTH_DEV_MODE", False))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("OTP delivery configuration"))
        self.stdout.write("")

        # ---- SMS ----
        if sms_key:
            masked = f"{sms_key[:4]}…{sms_key[-4:]}" if len(sms_key) > 10 else "set"
            self.stdout.write(
                f"  SMS (2Factor)   {self.style.SUCCESS('CONFIGURED')}   key {masked}"
            )
            self.stdout.write(
                f"                  base {settings.TWOFACTOR_BASE_URL}"
            )
            if not getattr(settings, "TWOFACTOR_SENDER_ID", ""):
                self.stdout.write(
                    "                  note: TWOFACTOR_SENDER_ID is empty; 2Factor may "
                    "require a DLT-approved sender for your account."
                )
        else:
            self.stdout.write(
                f"  SMS (2Factor)   {self.style.ERROR('NOT CONFIGURED')}   "
                "no SMS will be sent"
            )
            self.stdout.write(
                "                  fix: set TWOFACTOR_API_KEY in backend/.env, then restart"
            )

        # ---- Email ----
        if resend_key:
            masked = f"{resend_key[:6]}…{resend_key[-4:]}" if len(resend_key) > 12 else "set"
            self.stdout.write(
                f"  Email (Resend)  {self.style.SUCCESS('CONFIGURED')}   key {masked}"
            )
            sender = getattr(settings, "RESEND_FROM_EMAIL", "")
            self.stdout.write(f"                  from {sender}")
            if "onboarding@resend.dev" in sender:
                self.stdout.write(
                    "                  note: the resend.dev test sender only delivers to "
                    "the Resend account owner's own address."
                )
        elif email_service._smtp_is_real():
            self.stdout.write(
                f"  Email (SMTP)    {self.style.SUCCESS('CONFIGURED')}   host {email_host}"
            )
        else:
            self.stdout.write(
                f"  Email           {self.style.WARNING('LOCAL OUTBOX ONLY')}   "
                "nothing is sent"
            )
            self.stdout.write(
                "                  fix: set RESEND_API_KEY or EMAIL_HOST in backend/.env"
            )
            if getattr(settings, "EMAIL_CONSOLE_FALLBACK", False) and debug:
                self.stdout.write(
                    f"                  messages are written to {email_service.DEV_OUTBOX}"
                )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Codes in API responses"))
        if dev_mode and debug:
            self.stdout.write(
                f"  AUTH_DEV_MODE   {self.style.WARNING('ON')}   "
                "the response includes `dev_otp` so you can sign in without delivery"
            )
        elif dev_mode and not debug:
            self.stdout.write(
                f"  AUTH_DEV_MODE   {self.style.SUCCESS('EFFECTIVELY OFF')}   "
                "set but suppressed because DEBUG=False"
            )
        else:
            self.stdout.write(
                f"  AUTH_DEV_MODE   {self.style.SUCCESS('OFF')}   "
                "codes are never returned to clients"
            )

        # ---- optional live tests ----
        if options.get("send_to"):
            number = options["send_to"]
            self.stdout.write("")
            self.stdout.write(f"Sending a real SMS to {number} …")
            try:
                sms_service.send_otp_sms(mobile_number=number, code="123456")
                self.stdout.write(
                    self.style.SUCCESS(
                        "  SMS accepted by 2Factor. Check the handset. "
                        "(code sent was 123456 - it is not a valid login code)"
                    )
                )
            except sms_service.SMSDeliveryError as exc:
                self.stdout.write(self.style.ERROR(f"  FAILED: {exc}"))

        if options.get("send_email_to"):
            address = options["send_email_to"]
            self.stdout.write("")
            self.stdout.write(f"Sending a real email to {address} …")
            try:
                delivered = email_service.send_otp_email(
                    to=address,
                    code="123456",
                    purpose_label="Delivery test",
                    minutes=5,
                )
                if delivered:
                    self.stdout.write(self.style.SUCCESS("  Email accepted by the provider."))
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            "  NOT DELIVERED. No provider accepted it - see the table above."
                        )
                    )
            except email_service.EmailDeliveryError as exc:
                self.stdout.write(self.style.ERROR(f"  FAILED: {exc}"))

        self.stdout.write("")
