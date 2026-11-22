"""Inbound port used by OTHER MODULES: the quotations of a registered customer (US 2.20).

No ``Actor``: the calling module has already checked its own permission.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest


@dataclass(frozen=True, slots=True)
class CustomerQuotationView:
    id: UUID
    number: str
    issued_at: datetime
    status: str  # QuotationStatus value


class CustomerQuotations(ABC):
    @abstractmethod
    def quotations_of(
        self, customer_id: UUID, page_request: PageRequest
    ) -> Page[CustomerQuotationView]:
        """Newest first."""
