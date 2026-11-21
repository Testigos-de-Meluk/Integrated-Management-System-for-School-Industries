"""Django project configuration (settings, root URLs, WSGI/ASGI and Celery)."""

from .celery import app as celery_app

__all__ = ("celery_app",)
