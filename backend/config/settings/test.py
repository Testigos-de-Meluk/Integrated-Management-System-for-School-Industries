"""Settings for the automated test suite (synthetic data only, NFR-05-02)."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key")

from .base import *  # noqa: E402, F403

DEBUG = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
