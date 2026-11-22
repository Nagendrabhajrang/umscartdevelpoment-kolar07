"""Create the single UMS Mart admin account.

There is exactly one admin in this system and no public registration path. The
account is provisioned here, by an operator with shell access.

    python manage.py create_admin                       # prompts for a password
    python manage.py create_admin --rotate              # reset the password
    python manage.py create_admin --email ops@example.com

Re-running with ``--rotate`` re-provisions the existing admin rather than adding
a second one: the command refuses to create a duplicate.
"""

from getpass import getpass

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User, UserRole


class Command(BaseCommand):
    help = "Create (or rotate the password of) the single UMS Mart admin account."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=None, help="Admin login name")
        parser.add_argument("--email", default=None, help="Registered admin email (MFA destination)")
        parser.add_argument("--password", default=None, help="Password (omit to be prompted)")
        parser.add_argument(
            "--rotate",
            action="store_true",
            help="Re-provision the existing admin instead of creating a new one",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        username = options["username"] or settings.env_str("ADMIN_USERNAME", "admin") if hasattr(settings, "env_str") else (options["username"] or "admin")
        email = options["email"] or getattr(settings, "ADMIN_EMAIL", "") or None

        existing_admin = User.objects.filter(role=UserRole.ADMIN).first()

        if existing_admin and not options["rotate"]:
            raise CommandError(
                f"An admin account already exists ('{existing_admin.username}'). "
                "There may only be one. Use --rotate to reset its password."
            )

        if existing_admin and options["rotate"]:
            user = existing_admin
            self.stdout.write(f"Rotating password for existing admin '{user.username}'.")
        else:
            user = User(role=UserRole.ADMIN, username=username, email=email)

        password = options["password"]
        if not password:
            password = getpass("Admin password: ")
            confirm = getpass("Confirm password: ")
            if password != confirm:
                raise CommandError("Passwords do not match.")
            if len(password) < 10:
                raise CommandError("Use at least 10 characters.")

        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            raise CommandError("; ".join(exc.messages))

        with transaction.atomic():
            if options["email"]:
                user.email = options["email"]
            user.username = username
            user.role = UserRole.ADMIN
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.is_email_verified = True
            user.set_password(password)
            user.save()

        if not user.email:
            self.stdout.write(
                self.style.WARNING(
                    "No admin email set - MFA cannot send. Re-run with --email or set ADMIN_EMAIL."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Admin ready: username='{user.username}' email='{user.email or '—'}'"
            )
        )
