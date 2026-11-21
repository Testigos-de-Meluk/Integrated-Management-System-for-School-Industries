"""Celery application: background tasks and the periodic scheduler (Celery Beat)."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("imsi")
app.config_from_object("django.conf:settings", namespace="CELERY")
# Finds ``tasks.py`` inside each registered app, i.e. ``modules/<module>/infrastructure/tasks.py``.
app.autodiscover_tasks()
