#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path


def main():
    # `.env` chooses the settings module (development / sandbox / production).
    #
    # This has to happen HERE, before django.conf is imported: settings/base.py
    # loads the same file, but by then the module has already been imported and
    # `setdefault` below wins. That silent mismatch is what made the sandbox
    # preview report "this browser blocked the sign-in cookie" - `.env` said
    # config.settings.sandbox (SameSite=None) while the process really ran
    # development settings (SameSite=Lax), and a cross-site frame drops Lax
    # cookies.
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    except ImportError:  # pragma: no cover - dotenv is in requirements.txt
        pass

    # Default to development settings; production sets the variable in systemd.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and available "
            "on your PYTHONPATH environment variable? Did you forget to "
            "activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
