"""
UMS Mart - Base Django settings.

Contains configuration common to every environment. Neither
``development.py`` nor ``production.py`` should duplicate these values;
they only override what genuinely differs.

Environment variables are read from the process environment. A local
``.env`` file (see ``.env.example`` at the repository root) is loaded by
the ``development`` settings module only; production is expected to
provide real environment variables through systemd / the process manager.
"""

from pathlib import Path
import os

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# <repo>/backend/config/settings/base.py  ->  <repo>/backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# <repo>/backend                      ->  <repo>
REPO_ROOT = BASE_DIR.parent
# Convenience, mirrors the documented layout: ums_mart/backend/media
MEDIA_ROOT = BASE_DIR / "media"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Load a .env sitting next to backend/manage.py, or at the repository root.
for _candidate in (BASE_DIR / ".env", REPO_ROOT / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate, override=False)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def env(key, default=None):
    """Read a string environment variable (None-safe)."""
    return os.environ.get(key, default)


def env_bool(key, default=False):
    """Read a boolean environment variable accepting common truthy spellings."""
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_str(key, default=""):
    value = os.getenv(key)
    return value if value is not None and value != "" else default


def env_int(key, default=0):
    """Read an integer environment variable."""
    try:
        return int(os.environ[key])
    except (KeyError, TypeError, ValueError):
        return default


def env_list(key, default=None, separator=","):
    """Read a comma-separated environment variable into a list."""
    value = os.environ.get(key)
    if value is None or not value.strip():
        return list(default or [])
    return [item.strip() for item in value.split(separator) if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
]

# First-party modules. Each one declares an explicit AppConfig so the verbose
# names shown in the Django admin are human readable.
LOCAL_APPS = [
    "common",
    "apps.accounts.apps.AccountsConfig",
    "apps.authentication.apps.AuthenticationConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.customers.apps.CustomersConfig",
    "apps.catalog.apps.CatalogConfig",
    "apps.inventory.apps.InventoryConfig",
    "apps.cart.apps.CartConfig",
    "apps.wishlist.apps.WishlistConfig",
    "apps.addresses.apps.AddressesConfig",
    "apps.orders.apps.OrdersConfig",
    "apps.payments.apps.PaymentsConfig",
    "apps.promotions.apps.PromotionsConfig",
    "apps.banners.apps.BannersConfig",
    "apps.store_settings.apps.StoreSettingsConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.RequestLoggingMiddleware",
    "common.middleware.ApiExceptionMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Values are always driven by environment variables so that the same code
# base works on a Windows laptop and on a Hostinger VPS. PostgreSQL only.
# Percent-encoding is available through DATABASE_URL parsing (see below).
DB_ENGINE = "django.db.backends.postgresql"
DB_NAME = env("DB_NAME", "ums_mart_db")
DB_USER = env("DB_USER", "ums_mart_user")
DB_PASSWORD = env("DB_PASSWORD", "")
DB_HOST = env("DB_HOST", "127.0.0.1")
DB_PORT = env("DB_PORT", "5432")
DB_CONN_MAX_AGE = env_int("DB_CONN_MAX_AGE", 60)

DATABASES = {
    "default": {
        "ENGINE": DB_ENGINE,
        "NAME": DB_NAME,
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "CONN_MAX_AGE": DB_CONN_MAX_AGE,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "connect_timeout": env_int("DB_CONNECT_TIMEOUT", 10),
        },
        "ATOMIC_REQUESTS": False,
        "TEST": {
            "NAME": env("DB_TEST_NAME", f"test_{DB_NAME}"),
            "CHARSET": None,
            "COLLATION": None,
            "MIRROR": None,
        },
    }
}

# A single DATABASE_URL, when provided, wins over the discrete variables.
# Supported form: postgresql://user:password@host:port/dbname
DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    from urllib.parse import unquote, urlparse

    _url = urlparse(DATABASE_URL)
    if _url.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must be a postgresql:// URL for UMS Mart.")
    DATABASES["default"].update(
        {
            "NAME": unquote(_url.path.lstrip("/")),
            "USER": unquote(_url.username or ""),
            "PASSWORD": unquote(_url.password or ""),
            "HOST": _url.hostname or "127.0.0.1",
            "PORT": str(_url.port or "5432"),
        }
    )

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Password validation is configured further down this file, next to the rest of
# the authentication policy. It is deliberately NOT defined twice: the later
# assignment silently won, so a copy here would be dead code that looks
# authoritative and is not.

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = env("STATIC_URL", "/static/")
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
MEDIA_URL = env("MEDIA_URL", "/media/")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

STORAGES_DEVELOPMENT = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Round 30: Django session authentication, and nothing else. Requests carry
    # the HttpOnly session cookie; no token header exists any more.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.authentication.authentication.UmsSessionAuthentication",
    ],
    # Public catalogue browsing stays open; every write path and every
    # account/admin endpoint declares its own permission class.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": env_int("API_PAGE_SIZE", 20),
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "EXCEPTION_HANDLER": "common.exceptions.ums_mart_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON_RATE", "1000/hour"),
        "user": env("THROTTLE_USER_RATE", "10000/hour"),
    },
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%z",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "UMS Mart API",
    "DESCRIPTION": (
        "REST API for UMS Mart - Online Grocery & E-Commerce Platform.\n\n"
        "**Authentication is not implemented in this phase.** All endpoints are "
        "currently unauthenticated and must NOT be exposed publicly until the "
        "authentication phase (customer OTP + admin credentials + RBAC) ships. "
        "See `docs/AUTHENTICATION.md`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "OrderStatusEnum": "apps.orders.models.OrderStatus.choices",
        "OrderPaymentStatusEnum": "apps.orders.models.PaymentStatus.choices",
        "PaymentStatusEnum": "apps.payments.models.PaymentStatus.choices",
        "PaymentMethodEnum": "apps.payments.models.PaymentMethod.choices",
        "VerificationActionEnum": "apps.payments.models.VerificationAction.choices",
        "DiscountTypeEnum": "apps.promotions.models.DiscountType.choices",
        "PromotionAppliesToEnum": "apps.promotions.models.AppliesTo.choices",
        "AddressLabelEnum": "apps.addresses.models.AddressLabel.choices",
        "CartStatusEnum": "apps.cart.models.CartStatus.choices",
        # Product.Status is a nested class, so drf-spectacular cannot resolve it
        # from a dotted string - the choice tuples are given explicitly.
        "ProductStatusEnum": [
            ("draft", "Draft"),
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("discontinued", "Discontinued"),
        ],
        "CustomerStatusEnum": "apps.customers.models.CustomerStatus.choices",
        "RefundStatusEnum": "apps.payments.models.RefundStatus.choices",
        "CancellationReasonEnum": "apps.orders.models.CancellationReason.choices",
        "BannerPlacementEnum": "apps.banners.models.BannerPlacement.choices",
        "StockMovementTypeEnum": "apps.inventory.models.StockMovementType.choices",
    },
    "SORT_OPERATIONS": True,
    "TAGS": [
        {"name": "Customers", "description": "Customer profiles."},
        {"name": "Catalog", "description": "Categories, products, product images."},
        {"name": "Inventory", "description": "Stock levels and stock movement history."},
        {"name": "Cart", "description": "Shopping cart and cart items."},
        {"name": "Wishlist", "description": "Favourite products."},
        {"name": "Addresses", "description": "Customer delivery addresses."},
        {"name": "Orders", "description": "Checkout, order creation and order lifecycle."},
        {"name": "Payments", "description": "UPI QR and Cash on Delivery payments."},
        {"name": "Promotions", "description": "Offers, discounts and coupons."},
        {"name": "Banners", "description": "Homepage banners."},
        {"name": "Support", "description": "Complaints, tickets and replies."},
        {"name": "Store Settings", "description": "Delivery charges and store configuration."},
    ],
}

# ---------------------------------------------------------------------------
# CORS / CSRF (defaults are tightened in production.py)
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", [])
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", [])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-customer-id",
]

# ---------------------------------------------------------------------------
# Upload / business defaults
# ---------------------------------------------------------------------------
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 10)
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

# Identifier used by the (not yet implemented) authentication layer. Until
# then, customer-scoped endpoints resolve the caller via the "X-Customer-Id"
# header or the "customer" query parameter. See docs/AUTHENTICATION.md.
CUSTOMER_ID_HEADER = "X-Customer-Id"
CUSTOMER_ID_QUERY_PARAM = "customer"

# ---------------------------------------------------------------------------
# Logging (console only here; environments add file/rotating handlers)
# ---------------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} [{process:d}] {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {name} {message}", "style": "{"},
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": env("DB_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "common": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------
MONEY_MAX_DIGITS = 12
MONEY_DECIMAL_PLACES = 2

# Session/CSRF cookie names are namespaced so several projects can share a host.
SESSION_COOKIE_NAME = "ums_mart_sessionid"
CSRF_COOKIE_NAME = "ums_mart_csrftoken"
LANGUAGE_COOKIE_NAME = "ums_mart_language"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
from datetime import timedelta  # noqa: E402  (kept beside the config it serves)

# OTP policy. The values below are the documented development defaults; every
# one is overridable from the environment so production can tighten them.
OTP_LENGTH = env_int("OTP_LENGTH", 6)
OTP_VALIDITY_SECONDS = env_int("OTP_VALIDITY_SECONDS", 300)          # 5 minutes
OTP_RESEND_COOLDOWN_SECONDS = env_int("OTP_RESEND_COOLDOWN_SECONDS", 60)
OTP_MAX_ATTEMPTS = env_int("OTP_MAX_ATTEMPTS", 5)

# Rate limits: per account and per IP, per rolling window.
OTP_MAX_REQUESTS_PER_HOUR = env_int("OTP_MAX_REQUESTS_PER_HOUR", 5)
OTP_MAX_REQUESTS_PER_IP_PER_HOUR = env_int("OTP_MAX_REQUESTS_PER_IP_PER_HOUR", 20)

# Development convenience: when True the OTP is returned in the API response so
# the flow can be exercised without a provider. It is forced off whenever
# DEBUG is False, so a production deployment cannot leak codes by accident.
# NOTE: this cannot simply be `DEBUG and ...`. base.py defines DEBUG=False and
# development.py raises it to True *after* base.py has run, so evaluating here
# would bake in the base value. The effective flag is resolved lazily below.
AUTH_DEV_MODE = env_bool("AUTH_DEV_MODE", True)

ADMIN_EMAIL = env_str("ADMIN_EMAIL", "nagendrajoe@gmail.com")

# ---------------------------------------------------------------------------
# Sessions (round 30)
# ---------------------------------------------------------------------------
# Django's database-backed sessions are the whole authentication state now.
#
# The reason this round exists: every previous design put a token in the browser
# and then invented a way to invalidate it. Each of those was a path by which a
# perfectly healthy browser could be told it was signed out - an access token read
# as expired mid-page, a refresh that failed once, a rotation replay that missed
# its cache window. A session row has none of that: it is either there or it is
# not, and only the server decides.
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Seven days. Long enough that a shopper is not asked for an OTP every morning,
# short enough that a stolen cookie is not useful for a month.
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 24 * 7)

# Explicitly False: a session survives closing the browser. The requirement is
# that a shopper returning tomorrow is still signed in.
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# A session whose row is gone must not resurrect itself from the cookie.
SESSION_SAVE_EVERY_REQUEST = False

# The session id is a credential, so JavaScript must never be able to read it.
SESSION_COOKIE_HTTPONLY = True

# Lax rather than Strict: the storefront and the API share an origin through the
# dev proxy, and a top-level navigation into the site must still carry the cookie
# or the user appears signed out on arrival. Strict would break that.
SESSION_COOKIE_SAMESITE = "Lax"

SESSION_COOKIE_PATH = "/"

# The CSRF cookie is NOT HttpOnly: the browser has to read it to echo the token
# back in the X-CSRFToken header. That is how double-submit CSRF works, and it is
# safe because the token is useless without the session cookie, which JS cannot
# read.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_PATH = "/"
CSRF_USE_SESSIONS = False

# The OTP flow authenticates out-of-band, so there is no password to hand to
# ModelBackend. One backend, and it only ever confirms an identity the OTP code
# has already proven.
AUTHENTICATION_BACKENDS = ["apps.authentication.backends.OTPBackend"]

# --- OTP delivery providers ------------------------------------------------
# Credentials come from the environment only; nothing is hardcoded here.
TWOFACTOR_API_KEY = env_str("TWOFACTOR_API_KEY", "")
TWOFACTOR_BASE_URL = env_str("TWOFACTOR_BASE_URL", "https://2factor.in/API/V1")
TWOFACTOR_SENDER_ID = env_str("TWOFACTOR_SENDER_ID", "")

RESEND_API_KEY = env_str("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = env_str("RESEND_FROM_EMAIL", "onboarding@resend.dev")
RESEND_API_URL = env_str("RESEND_API_URL", "https://api.resend.com/emails")

# When True and DEBUG is on, emails are written to the console and a mail
# outbox instead of being sent. Real providers are used as soon as credentials
# are present.
EMAIL_CONSOLE_FALLBACK = env_bool("EMAIL_CONSOLE_FALLBACK", True)

# --- Password hashing ------------------------------------------------------
# Argon2 first (memory-hard), PBKDF2 second so existing hashes keep verifying.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": env_int("PASSWORD_MIN_LENGTH", 10)}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


def dev_mode_active() -> bool:
    """Is the OTP-in-response development aid allowed to run?

    Both conditions must hold, and DEBUG is checked at call time so the value
    from ``development.py`` (or ``production.py``) is the one that counts. A
    production deployment therefore cannot expose codes even if AUTH_DEV_MODE is
    left set in the environment: DEBUG is False there.
    """
    from django.conf import settings as dj_settings

    return bool(getattr(dj_settings, "AUTH_DEV_MODE", False)) and bool(dj_settings.DEBUG)
