"""
UMS Mart - sandbox preview settings.

Development settings plus the two things the hosted preview needs. Use it only
when the apps are opened through the HTTPS preview host
(https://<port>-<sandbox-id>.e2b.app), where every app is shown inside a frame
that belongs to a different site:

    DJANGO_SETTINGS_MODULE=config.settings.sandbox python manage.py runserver 0.0.0.0:8000

On a normal machine keep using config.settings.development.
"""

import os

# 1. Cookies must be SameSite=None; Secure to be stored inside a cross-site
#    frame. development.py reads this switch at import time, so set it first.
os.environ.setdefault("COOKIE_CROSS_SITE", "1")

from .development import *  # noqa: E402,F401,F403

# 2. The API's own pages (/, /api/docs/, /health/) are shown in that frame too.
#    X-Frame-Options has no "allow this other site" value, so the header is
#    dropped here. Never do this in production.
MIDDLEWARE = [m for m in MIDDLEWARE if "XFrameOptionsMiddleware" not in m]  # noqa: F405
