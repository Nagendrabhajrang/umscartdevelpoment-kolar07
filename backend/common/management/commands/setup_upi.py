"""Make sure the store can actually take UPI money.

Run this when the storefront or the admin console shows no UPI option, no UPI ID
and no QR - the usual cause is a database that was created before the UPI fields
were added, or a store-settings row whose ``upi_id`` is still empty.

    python manage.py setup_upi                       # fill anything missing
    python manage.py setup_upi --upi-id you@bank     # set / replace the UPI ID
    python manage.py setup_upi --payee "UMS Mart"    # set the payee name
    python manage.py setup_upi --disable              # switch UPI off again
    python manage.py setup_upi --regenerate-qr        # redraw the QR from the ID

It is idempotent: it only writes what is missing, and it never touches values an
admin has already entered (unless you pass the matching flag).
"""

from django.core.management.base import BaseCommand, CommandError

from apps.store_settings.models import StoreSettings
from apps.store_settings.services import generate_upi_qr_image

DEFAULT_UPI_ID = "umsmart@okhdfcbank"
DEFAULT_PAYEE = "UMS Mart"


class Command(BaseCommand):
    help = "Fill in the store's UPI settings (ID, payee, QR) so UPI shows up in the apps."

    def _load_settings(self):
        """StoreSettings.load(), but with a readable error when the DB is down.

        Without this, a missing DB_PASSWORD in backend/.env prints a 60-line
        psycopg traceback and it looks like the command itself is broken.
        """
        from django.db import OperationalError, connections

        cfg = connections["default"].settings_dict
        try:
            return StoreSettings.load()
        except OperationalError as exc:
            raise CommandError(
                "Cannot reach PostgreSQL, so the UPI settings cannot be saved.\n"
                f"  {exc}\n"
                f"  host {cfg.get('HOST')}:{cfg.get('PORT')}  db {cfg.get('NAME')}  "
                f"user {cfg.get('USER')}  "
                f"password {'(set)' if cfg.get('PASSWORD') else '(EMPTY)'}\n"
                "Fix backend/.env (copy .env.example if it is missing):\n"
                "  DB_NAME=ums_mart_db\n  DB_USER=ums_mart_user\n"
                "  DB_PASSWORD=<the password you gave that role>\n"
                "  DB_HOST=127.0.0.1\n  DB_PORT=5432\n"
                "or one line:\n"
                "  DATABASE_URL=postgresql://ums_mart_user:PASSWORD@127.0.0.1:5432/ums_mart_db\n"
                "Then: python manage.py migrate && python manage.py setup_upi"
            ) from exc

    def add_arguments(self, parser):
        parser.add_argument("--upi-id", default="", help="UPI ID to store, e.g. store@okhdfcbank.")
        parser.add_argument("--payee", default="", help="Payee name shown to the customer.")
        parser.add_argument("--disable", action="store_true", help="Switch UPI off.")
        parser.add_argument(
            "--regenerate-qr",
            action="store_true",
            help="Redraw the QR image from the current UPI ID.",
        )

    def handle(self, *args, **options):
        settings_obj = self._load_settings()
        changed = []

        if options["upi_id"]:
            settings_obj.upi_id = options["upi_id"].strip()
            changed.append("upi_id")
        elif not (settings_obj.upi_id or "").strip():
            settings_obj.upi_id = DEFAULT_UPI_ID
            changed.append("upi_id (default)")

        if options["payee"]:
            settings_obj.upi_payee_name = options["payee"].strip()
            changed.append("upi_payee_name")
        elif not (settings_obj.upi_payee_name or "").strip():
            settings_obj.upi_payee_name = DEFAULT_PAYEE
            changed.append("upi_payee_name (default)")

        if options["disable"]:
            settings_obj.upi_enabled = False
            changed.append("upi_enabled=False")
        elif not settings_obj.upi_enabled:
            settings_obj.upi_enabled = True
            changed.append("upi_enabled=True")

        if changed:
            settings_obj.save()
        for name in changed:
            self.stdout.write(f"  set {name}")

        needs_qr = options["regenerate_qr"] or not settings_obj.upi_qr_image
        if needs_qr:
            try:
                name = generate_upi_qr_image(settings_obj)
            except Exception as exc:  # noqa: BLE001 - report, do not crash the command
                self.stdout.write(self.style.WARNING(f"  QR not generated: {exc}"))
            else:
                if name:
                    self.stdout.write(f"  QR written to {name}")
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "  QR not generated: install segno (pip install -r requirements.txt)"
                        )
                    )

        settings_obj.refresh_from_db()
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Store UPI settings now:"))
        self.stdout.write(f"  upi_enabled   : {settings_obj.upi_enabled}")
        self.stdout.write(f"  upi_id        : {settings_obj.upi_id or '(empty)'}")
        self.stdout.write(f"  payee name    : {settings_obj.upi_payee_name or '(empty)'}")
        self.stdout.write(
            f"  QR image      : {settings_obj.upi_qr_image.name if settings_obj.upi_qr_image else '(none)'}"
        )
        if settings_obj.upi_qr_image:
            self.stdout.write(
                f"  QR URL        : /media/{settings_obj.upi_qr_image.name}"
            )
        self.stdout.write("")
        self.stdout.write(
            "Checkout now offers UPI, and Settings -> Payments shows these values."
        )
