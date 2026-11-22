"""Base Django settings shared by every environment.

All environment-specific values come from environment variables (see ``.env.example`` at the
repository root). Never hard-code secrets here.
"""

import hashlib
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# --- Core -------------------------------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Each business module registers its Django app from its infrastructure layer, so models and
# migrations live in ``modules/<module>/infrastructure/``.
BUSINESS_MODULES = [
    "shared_kernel",
    "authentication",
    "user_accounts",
    "products",
    "customers",
    "chatbot",
    "quotations",
    "work_orders",
    "accounting_export",
    "backups",
    "price_history",
]

INSTALLED_APPS = [
    "rest_framework",
    "drf_spectacular",
    *[f"modules.{module}.infrastructure" for module in BUSINESS_MODULES],
]

# Pure JSON API: no Django sessions, CSRF or admin. Authentication (JWT + TOTP) is implemented
# by the ``authentication`` module.
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

# --- Database ---------------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "imsi"),
        "USER": env("POSTGRES_USER", "imsi"),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
        # NFR-04-02: every API request runs in one ACID transaction (Read Committed, the
        # PostgreSQL default). A failure anywhere — business rule, audit entry — rolls back all.
        "ATOMIC_REQUESTS": True,
        "CONN_MAX_AGE": 60,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Internationalization ---------------------------------------------------------------------

LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True  # Stored in UTC, displayed in America/Bogota (NFR-08-01).

# --- Django REST Framework --------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    # Access token + server-side session check on every request (FR-01-05, FR-01-06).
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "modules.authentication.infrastructure.api.authentication.SessionJwtAuthentication"
    ],
    # Authorization is enforced by every use case (actor.require(...)): deny by default.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    # NFR-07-02: server-side pagination, never more than 50 records per page.
    "DEFAULT_PAGINATION_CLASS": (
        "modules.shared_kernel.infrastructure.api.pagination.StandardPagination"
    ),
    "PAGE_SIZE": 20,
    # OpenAPI 3 schema generated from views and serializers (drf-spectacular).
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Single error format: {"detail": "...", "errors": {"field": ["..."]}}.
    # Public endpoints (virtual assistant) are rate-limited per IP address.
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "public_catalog": env("THROTTLE_PUBLIC_CATALOG", "120/min"),
        "public_estimate": env("THROTTLE_PUBLIC_ESTIMATE", "60/min"),
        "public_quotation": env("THROTTLE_PUBLIC_QUOTATION", "10/hour"),
        "public_document": env("THROTTLE_PUBLIC_DOCUMENT", "60/hour"),
        "public_proposal": env("THROTTLE_PUBLIC_PROPOSAL", "20/hour"),
    },
    # Number of reverse proxies in front of Django: the client IP is taken from X-Forwarded-For
    # only behind them (0 = use the direct connection address, never a header the client sets).
    "NUM_PROXIES": int(env("NUM_PROXIES", "0")),
    "EXCEPTION_HANDLER": (
        "modules.shared_kernel.infrastructure.api.exceptions.api_exception_handler"
    ),
}

# --- API documentation (drf-spectacular) ------------------------------------------------------
# Swagger UI: /api/docs/   ReDoc: /api/redoc/   Raw schema: /api/schema/

SPECTACULAR_SETTINGS = {
    "TITLE": "IMSI API",
    "DESCRIPTION": (
        "REST API of the Integrated Management System for School Industries "
        "(Industrias Escolares). Each tag groups the endpoints of one module."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/",
    # Separate request/response components, so read-only fields are not required on input.
    "COMPONENT_SPLIT_REQUEST": True,
    # Explicit names for enums that share a field name across modules (e.g. "status").
    # Products and accounts share the same ACTIVE/INACTIVE set, so they share one enum.
    "ENUM_NAME_OVERRIDES": {
        "ActiveStatusEnum": "modules.products.ports.inbound.product_use_cases.PRODUCT_STATUSES",
        "RoleEnum": "modules.user_accounts.ports.inbound.user_account_use_cases.ROLES",
        "QuotationStatusEnum": (
            "modules.quotations.ports.inbound.quotation_review.QUOTATION_STATUSES"
        ),
    },
}

# --- Cache (rate limits) --------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", "redis://redis:6379/0"),
    }
}

# --- Quotations -----------------------------------------------------------------------------------

QUOTATION_VALIDITY_DAYS = int(env("QUOTATION_VALIDITY_DAYS", "15"))
PRICE_LOOKBACK_DAYS = int(env("PRICE_LOOKBACK_DAYS", "365"))

# --- AI provider (OpenAI-compatible: OpenRouter by default) -------------------------------------
# Without LLM_API_KEY the AI features are off: the free-text option is hidden and prices come only
# from statistics.
LLM_BASE_URL = env("LLM_BASE_URL", "https://openrouter.ai/api/v1")
LLM_API_KEY = env("LLM_API_KEY", "")
LLM_MODEL = env("LLM_MODEL", "google/gemma-4-31b-it:free")
LLM_TIMEOUT_SECONDS = float(env("LLM_TIMEOUT_SECONDS", "20"))
# Header name for a per-call session id, only for providers that require one
# (OpenCode Go: "x-opencode-session"). Empty = not sent.
LLM_SESSION_HEADER = env("LLM_SESSION_HEADER", "")
AI_PRICE_CACHE_SECONDS = int(env("AI_PRICE_CACHE_SECONDS", str(6 * 3600)))

# --- Redis / Celery ---------------------------------------------------------------------------

REDIS_URL = env("REDIS_URL", "redis://redis:6379/0")

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
# Periodic tasks (e.g. the 18:00 daily backup, FR-01-07) are registered here by their modules.
CELERY_BEAT_SCHEDULE: dict = {}

# --- Email ------------------------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", "mailpit")
EMAIL_PORT = int(env("EMAIL_PORT", "1025"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "IMSI <no-reply@industriasescolares.local>")

# --- Security ---------------------------------------------------------------------------------

# NFR-01-02: bcrypt cost factor (minimum 12). Only the test settings lower it, for speed.
BCRYPT_ROUNDS = int(env("BCRYPT_ROUNDS", "12"))

# JWT (PyJWT, HS256). Use a long random value in production. When empty, a 64-character key is
# derived from SECRET_KEY, so it is never shorter than the 32 bytes HS256 needs.
JWT_SIGNING_KEY = (
    env("JWT_SIGNING_KEY", "") or hashlib.sha256(f"jwt:{SECRET_KEY}".encode()).hexdigest()
)
ACCESS_TOKEN_MINUTES = int(env("ACCESS_TOKEN_MINUTES", "5"))
REFRESH_TOKEN_HOURS = int(env("REFRESH_TOKEN_HOURS", "12"))
# The refresh cookie is "Secure" (HTTPS only) everywhere except local development over HTTP.
REFRESH_COOKIE_SECURE = env_bool("REFRESH_COOKIE_SECURE", True)

# Fernet key that encrypts TOTP secrets at rest. Generate one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Empty → derived from SECRET_KEY (acceptable only in development).
TOTP_ENCRYPTION_KEY = env("TOTP_ENCRYPTION_KEY", "")

# Public URL of the frontend, used in emails (e.g. the login link sent with new credentials).
FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173")

# --- Files ------------------------------------------------------------------------------------

MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

# --- Logging (stdout, so `docker compose logs` shows everything) ------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
