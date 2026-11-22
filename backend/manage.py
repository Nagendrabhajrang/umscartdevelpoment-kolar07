#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path


def main():
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
