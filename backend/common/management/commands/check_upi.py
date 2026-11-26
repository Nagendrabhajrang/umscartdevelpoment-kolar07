"""Report whether this checkout really has the UPI feature, and whether the store
is configured to take UPI money.

    python manage.py check_upi

Three questions, because they fail differently:

* **Code** - is the UPI feature present in the files on THIS machine? A patch that
  did not apply (or a stale frontend bundle) looks exactly like "UPI is not
  displaying", so each check names the file to look at.
* **Database** - can Django even reach PostgreSQL? A wrong password in
  `backend/.env` produces a 60-line traceback and no useful answer, so it is
  reported here as one line, with the values Django actually used.
* **Data** - does the store-settings row have a UPI ID, a payee and a QR? An empty
  `upi_id` hides UPI everywhere; `manage.py setup_upi` fills it.

Exit codes: 0 = everything fine, 1 = code missing, 2 = database unreachable.
"""

import os
import pathlib

from django.core.management.base import BaseCommand

CODES = [
    ("admin Payments: 'Confirm UPI payment' button",
     "frontend/admin-dashboard/src/pages/Payments/PaymentsPage.jsx", "Confirm UPI payment"),
    ("admin Settings: UPI ID field",
     "frontend/admin-dashboard/src/pages/Settings/SettingsPage.jsx", "UPI ID"),
    ("admin Orders: delivery gated on the UPI payment",
     "frontend/admin-dashboard/src/pages/Orders/OrderDetailsPage.jsx", "delivery unlocks after that"),
    ("customer checkout: UPI offered from store settings",
     "frontend/customer-web/src/pages/Checkout/CheckoutPage.jsx", "upiOffered"),
    ("customer: transaction-ID popup",
     "frontend/customer-web/src/components/payment/UpiReferenceModal.jsx", "Confirm your UPI payment"),
    ("customer: UPI box component",
     "frontend/customer-web/src/components/payment/UpiPayBox.jsx", "Pay by UPI"),
    ("backend: UPI delivery rule",
     "backend/apps/orders/services.py", "upi_payment_not_confirmed"),
    ("backend: UPI fields on store settings",
     "backend/apps/store_settings/models.py", "upi_id"),
]


class Command(BaseCommand):
    help = "Check that the UPI feature and the store's UPI settings are in place."

    def handle(self, *args, **options):
        # .../backend/common/management/commands/check_upi.py -> repo root
        root = pathlib.Path(__file__).resolve().parents[4]
        missing = 0
        self.stdout.write(self.style.MIGRATE_HEADING("Code"))
        for label, rel, needle in CODES:
            path = root / rel
            ok = path.is_file() and needle in path.read_text(encoding="utf-8", errors="ignore")
            missing += 0 if ok else 1
            mark = self.style.SUCCESS("  OK  ") if ok else self.style.ERROR("  MISS")
            self.stdout.write(f"{mark} {label}")

        self.stdout.write("")
        if missing:
            self.stdout.write(self.style.ERROR(
                f"{missing} code check(s) missing: the patch is not applied in {root}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"All {len(CODES)} code checks pass in {root}"
            ))

        self.stdout.write("")
        self._report_config()

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Database + store settings"))
        if not self._report_store_settings():
            raise SystemExit(1 if missing else 2)

        self.stdout.write("")
        self.stdout.write(
            "Reminder: the browser only runs the new UI after the frontend is "
            "rebuilt or its dev server is restarted, and the API must be "
            "restarted after backend edits."
        )
        if missing:
            raise SystemExit(1)

    # -- helpers -----------------------------------------------------------
    def _report_config(self):
        """Show where the database settings came from.

        The classic failure is a missing backend/.env: Django then runs on the
        built-in defaults (db `ums_mart_db`, user `ums_mart_user`, empty
        password) and PostgreSQL answers `fe_sendauth: no password supplied`,
        which looks like a database problem but is a config problem.
        """
        from django.conf import settings as dj_settings

        root = pathlib.Path(__file__).resolve().parents[4]
        env_path = pathlib.Path(getattr(dj_settings, "BASE_DIR", root / "backend")) / ".env"
        cfg = dj_settings.DATABASES["default"]

        self.stdout.write(self.style.MIGRATE_HEADING("Config"))
        self.stdout.write(f"  settings module : {dj_settings.SETTINGS_MODULE}")
        if env_path.is_file():
            size = env_path.stat().st_size
            self.stdout.write(f"  .env file       : {env_path}  (FOUND, {size} bytes)")
        else:
            self.stdout.write(self.style.ERROR(
                f"  .env file       : {env_path}  (NOT FOUND)"
            ))

        keys = ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT")
        values = {
            "DB_NAME": cfg.get("NAME"),
            "DB_USER": cfg.get("USER"),
            "DB_PASSWORD": cfg.get("PASSWORD"),
            "DB_HOST": cfg.get("HOST"),
            "DB_PORT": cfg.get("PORT"),
        }
        for key in keys:
            value = values[key]
            if key == "DB_PASSWORD":
                shown = "(set)" if value else "(empty)"
            else:
                shown = value or "(empty)"
            origin = "from .env / environment" if os.environ.get(key) else "BUILT-IN DEFAULT"
            self.stdout.write(f"  {key:<16}: {shown}   [{origin}]")

        if not os.environ.get("DATABASE_URL") and not os.environ.get("DB_PASSWORD"):
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "  No DB_PASSWORD is reaching Django, so it is using the built-in "
                "defaults (db 'ums_mart_db', user 'ums_mart_user', no password)."
            ))
            self.stdout.write(
                "  Fix it with:  powershell -ExecutionPolicy Bypass -File fix_env.ps1"
            )
            self.stdout.write(
                "  ...or copy the tracked backend.env to backend\\.env (keep the name .env, "
                "not .env.txt, and save it as UTF-8, not UTF-16)."
            )
        return True

    def _report_store_settings(self):
        """Dump the UPI settings. Returns False when the database is unusable."""
        from django.db import OperationalError, connections

        conn = connections["default"]
        cfg = conn.settings_dict
        try:
            with conn.cursor():
                pass
        except OperationalError as exc:
            # A connection failure is NOT a patch problem, and a Django traceback
            # here hides that. Say plainly what is wrong and how to fix it.
            self.stdout.write(self.style.ERROR(f"  DATABASE UNREACHABLE: {exc}"))
            self.stdout.write("")
            self.stdout.write(f"  engine  : {cfg.get('ENGINE')}")
            self.stdout.write(f"  host    : {cfg.get('HOST')}:{cfg.get('PORT')}")
            self.stdout.write(f"  db      : {cfg.get('NAME')}")
            self.stdout.write(f"  user    : {cfg.get('USER')}")
            self.stdout.write(
                "  password: "
                + ("(SET)" if cfg.get("PASSWORD") else "(EMPTY - this is the problem)")
            )
            self.stdout.write("")
            self.stdout.write("  The code checks above are still valid; only the database part failed.")
            self.stdout.write("  Fix backend/.env (copy .env.example if the file is missing):")
            self.stdout.write("    DB_NAME=ums_mart_db")
            self.stdout.write("    DB_USER=ums_mart_user")
            self.stdout.write("    DB_PASSWORD=<the password you gave that role>")
            self.stdout.write("    DB_HOST=127.0.0.1")
            self.stdout.write("    DB_PORT=5432")
            self.stdout.write("  ...or replace all of those with one line:")
            self.stdout.write(
                "    DATABASE_URL=postgresql://ums_mart_user:PASSWORD@127.0.0.1:5432/ums_mart_db"
            )
            self.stdout.write("  then re-run: python manage.py migrate")
            return False

        try:
            from apps.store_settings.selectors import get_store_settings

            store = get_store_settings()
        except Exception as exc:  # noqa: BLE001 - surface anything, never a traceback
            self.stdout.write(self.style.ERROR(f"  Could not read store settings: {exc}"))
            self.stdout.write(
                "  The database is reachable but the tables are not ready: "
                "run `python manage.py migrate`."
            )
            return False

        self.stdout.write(f"  upi_enabled   : {store.upi_enabled}")
        self.stdout.write(
            f"  upi_id        : {store.upi_id or '(EMPTY - UPI is hidden in both apps)'}"
        )
        self.stdout.write(f"  payee name    : {store.upi_payee_name or '(empty)'}")
        self.stdout.write(
            "  QR image      : "
            + (store.upi_qr_image.name if store.upi_qr_image else "(none - run setup_upi --regenerate-qr)")
        )
        if store.upi_qr_image:
            self.stdout.write(f"  QR URL        : /media/{store.upi_qr_image.name}")
        if not store.upi_enabled or not (store.upi_id or "").strip():
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "  UPI is NOT offered to customers right now. Fix with: "
                "python manage.py setup_upi"
            ))
        return True
