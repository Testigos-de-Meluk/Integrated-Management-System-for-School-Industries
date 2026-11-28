"""Domain events of the Work Orders module (Observer pattern, NFR-05-01)."""

from dataclasses import dataclass
from uuid import UUID

from modules.shared_kernel.domain.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkOrderGenerated(DomainEvent):
    """A new O.T. enters the Siigo export queue (FR-02-16; subscriber added in step 5c)."""

    work_order_id: UUID
    number: str
    quotation_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkOrderCancelled(DomainEvent):
    """An annulled O.T. leaves the export queue if it was not exported yet (step 5c)."""

    work_order_id: UUID
    number: str
