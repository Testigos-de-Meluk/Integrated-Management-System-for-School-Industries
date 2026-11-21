"""Celery tasks of the shared kernel (discovered automatically by ``app.autodiscover_tasks``)."""

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(
    autoretry_for=(OSError,), retry_backoff=True, retry_kwargs={"max_retries": 5}, acks_late=True
)
def send_email(to: list[str], subject: str, body: str) -> None:
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to, fail_silently=False)
