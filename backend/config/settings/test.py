"""Settings for the automated test suite (synthetic data only, NFR-05-02)."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key")

from .base import *  # noqa: E402, F403

DEBUG = False
BCRYPT_ROUNDS = 4  # fast hashing in tests only (real environments use 12)
REFRESH_COOKIE_SECURE = False
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Tests run against PostgreSQL (inside Docker). TEST_DATABASE=sqlite allows a quick run on a
# machine without PostgreSQL; the official suite always uses PostgreSQL.
if os.environ.get("TEST_DATABASE") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
            "ATOMIC_REQUESTS": True,
        }
    }
