from abc import ABC, abstractmethod

from modules.shared_kernel.domain.notifications import EmailMessage


class Notifier(ABC):
    """Outbound port: delivers emails (credentials, quotations, backup alerts…)."""

    @abstractmethod
    def send(self, message: EmailMessage) -> None: ...
