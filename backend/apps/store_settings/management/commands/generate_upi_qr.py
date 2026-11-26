"""Render the store's UPI QR code from its UPI ID.

Admins can upload their own QR PNG in the console (Settings -> UPI). This
command is the alternative: type the UPI ID, let the backend draw the QR.

    python manage.py generate_upi_qr
    python manage.py generate_upi_qr --amount 324.80 --note UMS-2026-0001
"""

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from apps.store_settings.models import StoreSettings
from apps.store_settings.services import (
    build_upi_uri,
    generate_upi_qr_image,
)


class Command(BaseCommand):
    help = "Generate (or regenerate) the store UPI QR image from the configured UPI ID."

    def add_arguments(self, parser):
        parser.add_argument("--upi-id", default=None, help="Override the stored UPI ID.")
        parser.add_argument("--payee", default=None, help="Override the payee name.")
        parser.add_argument(
            "--amount", default=None,
            help="Fixed amount to bake into the QR (omit for an open-amount QR).",
        )
        parser.add_argument("--note", default="", help="Transaction note / order number.")

    def handle(self, *args, **options):
        settings_obj = StoreSettings.load()
        if options["upi_id"]:
            settings_obj.upi_id = options["upi_id"]
        if options["payee"]:
            settings_obj.upi_payee_name = options["payee"]

        amount = None
        if options["amount"]:
            try:
                amount = Decimal(str(options["amount"]))
            except InvalidOperation as exc:
                raise CommandError("--amount must be a number, e.g. 324.80") from exc

        name = generate_upi_qr_image(settings_obj, amount=amount, note=options["note"])
        if not name:
            raise CommandError("Could not generate the QR (is segno installed?)")

        self.stdout.write(self.style.SUCCESS(f"UPI QR saved to {name}"))
        self.stdout.write(f"  UPI ID : {settings_obj.upi_id}")
        self.stdout.write(f"  Payee  : {settings_obj.upi_payee_name or settings_obj.store_name}")
        self.stdout.write(f"  Intent : {build_upi_uri(settings_obj.upi_id, settings_obj.upi_payee_name, amount=amount, note=options['note'])}")
