"""
UMS Mart - Local development settings (Windows laptop / Linux dev box).

Run with:
    set DJANGO_SETTINGS_MODULE=config.settings.development     (Windows cmd)
    export DJANGO_SETTINGS_MODULE=config.settings.development   (bash)

Values come from the ``.env`` file at the repository root (see
``.env.example``). Nothing in this file is suitable for production.
"""

from .base import *  # noqa: F401,F403  (star import is intentional here)

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = True

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-key-do-not-use-in-production-ums-mart",
)

# Localhost variants plus ngrok/LAN testing hosts.
ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    ["localhost", "127.0.0.1", "[::1]", "0.0.0.0", "*.ngrok-free.app", "*"],
)

INTERNAL_IPS = ["127.0.0.1", "localhost"]

# ---------------------------------------------------------------------------
# Database - local PostgreSQL instance
# ---------------------------------------------------------------------------
DATABASES["default"]["OPTIONS"].update({"connect_timeout": 10})

# Uncomment to print every SQL statement while debugging a query.
# LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"

# ---------------------------------------------------------------------------
# Static files - served by runserver / WhiteNoise, no manifest hashing so
# that missing assets do not break the browsable API during development.
# ---------------------------------------------------------------------------
STORAGES = STORAGES_DEVELOPMENT

# ---------------------------------------------------------------------------
# Email - printed to the console during development
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# CORS / CSRF for the future React + Flutter clients running locally
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", True)
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # Round 30: the admin dashboard is its own dev origin, and with session
        # cookies it is a credentialed cross-origin client like the storefront.
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
)
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
)

# ---------------------------------------------------------------------------
# Preview/proxy origins (round 32)
# ---------------------------------------------------------------------------
# The sandbox preview serves the storefront from
# https://<port>-<sandbox-id>.e2b.app and renders it inside a frame whose
# top-level origin is different. That makes the storefront a *third-party*
# context, and a same-site-only (Lax) cookie is neither stored nor sent there.
#
# The visible symptom was brutal: the OTP was accepted, so the client showed the
# shopper as signed in, while every later request still ran anonymously and the
# guest basket had already been folded into an account the browser could not
# reach. Two items in, nothing out.
#
# Development only, therefore: accept any *.e2b.app origin, and let the session
# and CSRF cookies ride along cross-site (SameSite=None requires Secure, and the
# preview is HTTPS, so that is consistent). Production keeps the strict Lax
# policy from base.py - these lines must never be copied there.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[a-z0-9-]+\.e2b\.app$",
]

# Django understands `https://*.e2b.app` here, so the preview origin can submit
# unsafe requests (OTP verify, add-to-cart) without a CSRF rejection.
CSRF_TRUSTED_ORIGINS = CSRF_TRUSTED_ORIGINS + ["https://*.e2b.app"]

# Django cannot express "any port on this machine" in CSRF_TRUSTED_ORIGINS, so a
# dev server on an unexpected port (or a phone opening a LAN IP) had its unsafe
# requests rejected as if the page were untrusted. In DEBUG the check is widened
# to loopback and private-network origins; production is untouched. Set
# CSRF_ALLOW_LOCAL_ORIGINS=False in .env to keep the strict behaviour while
# developing.
if env_bool("CSRF_ALLOW_LOCAL_ORIGINS", True):
    MIDDLEWARE = [
        "common.middleware.DevOriginTolerantCsrfMiddleware"
        if entry == "django.middleware.csrf.CsrfViewMiddleware"
        else entry
        for entry in MIDDLEWARE
    ]


# ---------------------------------------------------------------------------
# Logging - verbose, human friendly
# ---------------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", "DEBUG")

LOGGING["handlers"]["console"]["formatter"] = "simple"
for _logger in ("django", "apps", "common"):
    LOGGING["loggers"][_logger]["level"] = LOG_LEVEL
LOGGING["root"]["level"] = LOG_LEVEL

# Show the Django debug toolbar automatically when it is installed.
if env_bool("USE_DEBUG_TOOLBAR", False):
    try:
        import debug_toolbar  # noqa: F401

        INSTALLED_APPS.append("debug_toolbar")
        MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    except ImportError:  # pragma: no cover - optional dependency
        pass

# ---------------------------------------------------------------------------
# Relaxed security so plain HTTP works on localhost
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Development convenience: browsable API is handy while building clients.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]


# Whether the browser will actually *store* those cookies is a separate question,
# and it depends on how the storefront is being served:
#
#   http://localhost:5173   same-site  -> Lax, not Secure. Works today; this is
#                                         the default and must stay the default.
#   https://…e2b.app/frame  cross-site -> needs SameSite=None; Secure, or the
#                                         session cookie is silently dropped.
#
# A cookie cannot be both, so this is an explicit switch rather than a guess.
# Enable it only when the storefront is opened through the HTTPS preview host:
#   COOKIE_CROSS_SITE=1 python manage.py runserver 0.0.0.0:8000
COOKIE_CROSS_SITE = env_bool("COOKIE_CROSS_SITE", False)

if COOKIE_CROSS_SITE:
    # SameSite=None REQUIRES Secure, and the preview is HTTPS, so the pair is
    # consistent. Never enable this over plain HTTP - the browser would drop the
    # session cookie and every request would arrive anonymous.
    SESSION_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # The frame is a different site, so responses must permit being framed.
    X_FRAME_OPTIONS = "SAMEORIGIN"
