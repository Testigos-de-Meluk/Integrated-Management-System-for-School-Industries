"""Celery tasks of the shared kernel (discovered automatically by ``app.autodiscover_tasks``)."""

import base64

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage


@shared_task(
    autoretry_for=(OSError,), retry_backoff=True, retry_kwargs={"max_retries": 5}, acks_late=True
)
def send_email(
    to: list[str], subject: str, body: str, attachments: list[list[str]] | None = None
) -> None:
    """``attachments`` = ``[[filename, base64 content, mimetype], ...]`` (task arguments must be
    JSON, so binary files travel base64-encoded)."""
    message = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, to)
    for filename, encoded, mimetype in attachments or []:
        message.attach(filename, base64.b64decode(encoded), mimetype)
    message.send(fail_silently=False)
