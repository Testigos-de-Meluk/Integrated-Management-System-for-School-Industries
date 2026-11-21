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

        transaction.on_commit(
            lambda: send_email.delay(list(message.to), message.subject, message.body)
        )
