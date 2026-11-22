"""
UMS Mart - Production settings (Hostinger VPS).

Run with:
    export DJANGO_SETTINGS_MODULE=config.settings.production

Security-relevant values are REQUIRED from the environment; the module
raises ``ImproperlyConfigured`` at import time when they are missing so a
misconfigured deployment fails loudly instead of silently running insecure.

Required environment variables in production:
    DJANGO_SECRET_KEY        long random string (>= 50 chars)
    DJANGO_ALLOWED_HOSTS     comma separated hostnames
    DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT  (or DATABASE_URL)
    CORS_ALLOWED_ORIGINS     comma separated https origins
    CSRF_TRUSTED_ORIGINS     comma separated https origins
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is required in production. "
        "Generate one with: python -c "
        "'from django.core.management.utils import get_random_secret_key; "
        "print(get_random_secret_key())'"
    )
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be a strong random value (>= 50 characters) "
        "and must not be the development placeholder."
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", env_list("ALLOWED_HOSTS", []))
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS is required in production, e.g. "
        "DJANGO_ALLOWED_HOSTS=api.umsmart.com,umsmart.com"
    )

# ---------------------------------------------------------------------------
# Database - production PostgreSQL
# ---------------------------------------------------------------------------
if not DATABASES["default"]["PASSWORD"]:  # noqa: F405
    raise ImproperlyConfigured(
        "DB_PASSWORD (or a password inside DATABASE_URL) is required in production."
    )
DATABASES["default"]["CONN_MAX_AGE"] = env_int("DB_CONN_MAX_AGE", 60)  # noqa: F405
DATABASES["default"]["OPTIONS"].update({"connect_timeout": 10})

# Persist connections between requests only behind a persistent worker
# (gunicorn sync workers are fine; keep CONN_MAX_AGE modest).

# ---------------------------------------------------------------------------
# HTTPS / cookies
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
# Deliberately opt-in: submitting a domain to the browser preload list is
# effectively irreversible, so it must never be enabled by accident. Flip
# SECURE_HSTS_PRELOAD=True in .env once every subdomain is HTTPS-only.
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # the React client reads it to send X-CSRFToken
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# Seven days, matching the requirement; base.py sets the same default and this
# makes the production value explicit and overridable.
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 24 * 7)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
# SESSION_COOKIE_DOMAIN is left unset: the storefront and the admin dashboard are
# expected to sit on the same registrable domain, and setting it to a bare
# "example.com" would leak the cookie to every sibling subdomain.

# ---------------------------------------------------------------------------
# Hosts / origins
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", [])
if not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured(
        "CORS_ALLOWED_ORIGINS is required in production, e.g. "
        "CORS_ALLOWED_ORIGINS=https://umsmart.com,https://admin.umsmart.com"
    )

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", CORS_ALLOWED_ORIGINS)

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_ROOT = env("STATIC_ROOT", str(BASE_DIR / "staticfiles"))  # noqa: F405
MEDIA_ROOT = env("MEDIA_ROOT", str(BASE_DIR / "media"))  # noqa: F405

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# ---------------------------------------------------------------------------
# Logging - rotating files, warnings and above to console
# ---------------------------------------------------------------------------
LOG_DIR = env("LOG_DIR", str(BASE_DIR / "logs"))  # noqa: F405
import os as _os  # noqa: E402

_os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} [{process:d}] {message}",
            "style": "{",
        },
        "json": {
            "format": (
                '{{"time": "{asctime}", "level": "{levelname}", '
                '"logger": "{name}", "message": "{message}"}}'
            ),
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": "WARNING",
        },
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": _os.path.join(LOG_DIR, "ums_mart.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
            "level": LOG_LEVEL,
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": _os.path.join(LOG_DIR, "errors.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
            "level": "ERROR",
        },
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
            "level": "ERROR",
        },
    },
    "root": {"handlers": ["console", "app_file"], "level": LOG_LEVEL},
    "loggers": {
        "django": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "error_file", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console", "error_file", "mail_admins"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["error_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "common": {
            "handlers": ["app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Email / admins
# ---------------------------------------------------------------------------
ADMINS = [("UMS Mart Admin", env("ADMIN_EMAIL", "admin@umsmart.local"))]
SERVER_EMAIL = env("SERVER_EMAIL", "no-reply@umsmart.local")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "UMS Mart <no-reply@umsmart.local>")

EMAIL_BACKEND = env(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 10

# ---------------------------------------------------------------------------
# API renderers - JSON only in production
# ---------------------------------------------------------------------------
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = ["rest_framework.renderers.JSONRenderer"]
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = [
    "rest_framework.throttling.AnonRateThrottle",
]
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": env("THROTTLE_ANON_RATE", "600/hour"),
    "user": env("THROTTLE_USER_RATE", "6000/hour"),
}

# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 10)
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Disable the browsable API entirely in production.
SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = (
    ["rest_framework.permissions.IsAdminUser"]
    if env_bool("DOCS_REQUIRE_ADMIN", False)
    else ["rest_framework.permissions.AllowAny"]
)
