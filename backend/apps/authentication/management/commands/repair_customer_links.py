"""Re-create any missing ``CustomerProfile`` links.

A sign-in only works if the ``accounts.User`` has a linked ``customers.Customer``
through ``accounts.CustomerProfile``. If that row goes missing - a manual data
fix, a restore, a cleanup script - the storefront used to sign the shopper out
immediately after login with "your session has expired".

The request path now repairs the link on demand, and this command repairs the
whole table in one go:

    python manage.py repair_customer_links
    python manage.py repair_customer_links --dry-run
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import CustomerProfile
from apps.authentication.services.auth_service import _ensure_customer_profile


class Command(BaseCommand):
    help = "Create the CustomerProfile link for any customer account missing one."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only.")

    def handle(self, *args, **options):
        User = get_user_model()
        missing = [
            user
            for user in User.objects.filter(role="CUSTOMER")
            if not CustomerProfile.objects.filter(user=user).exists()
        ]

        if not missing:
            self.stdout.write(self.style.SUCCESS("All customer accounts are linked."))
            return

        if options["dry_run"]:
            for user in missing:
                self.stdout.write(f"would repair user {user.pk} ({user.mobile_number})")
            self.stdout.write(self.style.WARNING(f"{len(missing)} account(s) need repair."))
            return

        repaired = 0
        for user in missing:
            try:
                profile = _ensure_customer_profile(user)
                self.stdout.write(
                    f"repaired user {user.pk} ({user.mobile_number}) -> customer "
                    f"{profile.customer_id}"
                )
                repaired += 1
            except Exception as exc:  # pragma: no cover - reported, not raised
                self.stderr.write(f"could not repair user {user.pk}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"{repaired} link(s) repaired."))
