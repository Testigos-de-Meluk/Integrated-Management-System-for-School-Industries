"""Test doubles for the shared kernel outbound ports (no database, no SMTP)."""

from modules.shared_kernel.domain.audit import AuditRecord
from modules.shared_kernel.domain.events import DomainEvent
from modules.shared_kernel.domain.notifications import EmailMessage
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger
from modules.shared_kernel.ports.outbound.event_publisher import EventPublisher
from modules.shared_kernel.ports.outbound.notifier import Notifier
from modules.shared_kernel.ports.outbound.password_hasher import PasswordHasher


class SpyAuditLogger(AuditLogger):
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def log(self, record: AuditRecord) -> None:
        self.records.append(record)


class SpyNotifier(Notifier):
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


class SpyEventPublisher(EventPublisher):
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


class FakePasswordHasher(PasswordHasher):
    """Reversible on purpose: only for tests."""

    def hash(self, raw_password: str) -> str:
        return f"hashed:{raw_password}"

    def matches(self, raw_password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{raw_password}"
