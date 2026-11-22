"""Domain events of the Quotations module (Observer pattern, NFR-05-01)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from modules.shared_kernel.domain.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class QuotationApproved(DomainEvent):
    """An approved quotation enters the export queue and can become a work order (step 5)."""

    quotation_id: UUID
    number: str
    customer_id: UUID | None
    approved_at: datetime
