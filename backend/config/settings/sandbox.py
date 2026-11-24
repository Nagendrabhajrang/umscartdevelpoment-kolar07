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

# Same DEBUG convenience as development.py: accept loopback / private-network
# origins, because the preview proxies requests and the browser origin is not the
# API host. CSRF_TRUSTED_ORIGINS still covers the *.e2b.app domains themselves.
if env_bool("CSRF_ALLOW_LOCAL_ORIGINS", True):  # noqa: F405
    MIDDLEWARE = [
        "common.middleware.DevOriginTolerantCsrfMiddleware"
        if m == "django.middleware.csrf.CsrfViewMiddleware"
        else m
        for m in MIDDLEWARE
    ]


# 3. Cookie-independent sign-in.
#
# The preview renders the storefront in a frame that belongs to another site, and
# browsers increasingly drop third-party cookies there - the login page then
# reports "this browser blocked the sign-in cookie". With this on, the login
# response also returns the session key and the SPA falls back to sending it as
# `Authorization: Bearer`. Development and production keep it off.
AUTH_BEARER_FALLBACK = True
