#!/usr/bin/env python
"""Run the end-to-end smoke suite from a normal (non-shell) process.

    python run_smoke.py                      # development settings
    DJANGO_SETTINGS_MODULE=config.settings.production python run_smoke.py

The suite creates its own run-scoped fixtures and cleans up afterwards, so it
can be executed repeatedly against a live database. It exits non-zero if any
check fails, which makes it usable as a deployment gate.

See docs/TESTING.md for what the 118 checks cover.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

from deployment.scripts.smoke_test import run  # noqa: E402

if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
