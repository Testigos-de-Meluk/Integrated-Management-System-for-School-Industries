"""Base Django settings shared by every environment.

All environment-specific values come from environment variables (see ``.env.example`` at the
repository root). Never hard-code secrets here.
"""

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
        # NFR-04-02: at least Read Committed (PostgreSQL default). Critical use cases open
        # explicit transactions in the application layer.
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
    # Temporary until the authentication module provides JWT authentication and RBAC.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
    # NFR-07-02: server-side pagination, never more than 50 records per page.
    "DEFAULT_PAGINATION_CLASS": (
        "modules.shared_kernel.infrastructure.api.pagination.StandardPagination"
    ),
    "PAGE_SIZE": 20,
    # OpenAPI 3 schema generated from views and serializers (drf-spectacular).
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
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
}

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
