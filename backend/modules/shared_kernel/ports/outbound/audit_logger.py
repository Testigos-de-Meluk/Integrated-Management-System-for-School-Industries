from abc import ABC, abstractmethod

from modules.shared_kernel.domain.audit import AuditRecord


class AuditLogger(ABC):
    """Outbound port: records critical actions in the audit log."""

    @abstractmethod
    def log(self, record: AuditRecord) -> None: ...
