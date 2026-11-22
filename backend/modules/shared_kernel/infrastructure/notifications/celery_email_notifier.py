import base64

from django.db import transaction

from modules.shared_kernel.domain.notifications import EmailMessage
from modules.shared_kernel.ports.outbound.notifier import Notifier


class CeleryEmailNotifier(Notifier):
    """Sends emails in the background through Celery, only after the transaction commits.

    - The request does not wait for the SMTP server.
    - If the use case fails and rolls back, no email is sent (no credentials for a user that was
      never created).
    """

    def send(self, message: EmailMessage) -> None:
        from modules.shared_kernel.infrastructure.tasks import send_email

        # robust=True: if the broker is down, the failure is logged instead of turning an already
        # committed operation (e.g. a created account) into an error response.
        attachments = [
            [a.filename, base64.b64encode(a.content).decode("ascii"), a.mimetype]
            for a in message.attachments
        ]
        transaction.on_commit(
            lambda: send_email.delay(list(message.to), message.subject, message.body, attachments),
            robust=True,
        )
