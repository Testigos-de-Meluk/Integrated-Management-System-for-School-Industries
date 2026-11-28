"""Siigo export queue (FR-02-16 … FR-02-18, step 5 decisions).

The queue holds **work orders**. An O.T. enters when it is generated, leaves when it is exported
(step 5d) and is **withdrawn** — never deleted, so the trace of when it entered stays — if it is
annulled before being exported. Withdrawn entries never show up in the queue.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class QueueStatus(StrEnum):
    PENDING_EXPORT = "PENDING_EXPORT"  # "Pendiente de exportar"
    EXPORTED = "EXPORTED"  # "Exportada" (step 5d)
    WITHDRAWN = "WITHDRAWN"  # "Retirada": annulled before export


@dataclass(eq=False, slots=True)
class QueueEntry:
    work_order_id: UUID
    enqueued_at: datetime
    status: QueueStatus = QueueStatus.PENDING_EXPORT
    withdrawn_at: datetime | None = None
    exported_at: datetime | None = None
    export_batch_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)

    @classmethod
    def enqueue(cls, work_order_id: UUID, now: datetime) -> "QueueEntry":
        return cls(work_order_id=work_order_id, enqueued_at=now)

    @property
    def is_pending(self) -> bool:
        return self.status is QueueStatus.PENDING_EXPORT

    def withdraw(self, now: datetime) -> bool:
        """The O.T. was annulled. Returns ``False`` if it had already been exported (or withdrawn):
        an exported O.T. is annulled in Siigo by hand, the queue keeps its record."""
        if not self.is_pending:
            return False
        self.status = QueueStatus.WITHDRAWN
        self.withdrawn_at = now
        return True
