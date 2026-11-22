from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from modules.customers.domain.commercial_note import CommercialNote
from modules.customers.domain.customer import Customer
from modules.customers.ports.inbound.customer_use_cases import CustomerFilters
from modules.shared_kernel.domain.pagination import Page, PageRequest


class CustomerRepository(ABC):
    @abstractmethod
    def get_by_id(self, customer_id: UUID) -> Customer | None: ...

    @abstractmethod
    def get_by_tax_id(self, tax_id: str) -> Customer | None: ...

    @abstractmethod
    def add(self, customer: Customer) -> None:
        """Raises ``DuplicateTaxId`` if the NIT/document already exists."""

    @abstractmethod
    def update(self, customer: Customer) -> None: ...

    @abstractmethod
    def search(self, filters: CustomerFilters, page_request: PageRequest) -> Page[Customer]:
        """One page matching every filter, ordered by name."""


class NoteRepository(ABC):
    @abstractmethod
    def get(self, note_id: UUID) -> CommercialNote | None: ...

    @abstractmethod
    def add(self, note: CommercialNote) -> None: ...

    @abstractmethod
    def update(self, note: CommercialNote) -> None: ...

    @abstractmethod
    def delete(self, note_id: UUID) -> None: ...

    @abstractmethod
    def list_for_customer(
        self, customer_id: UUID, page_request: PageRequest
    ) -> Page[CommercialNote]:
        """Newest first."""


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    document_type: str
    reference: str
    date: datetime
    status: str


class CommercialHistoryProvider(ABC):
    """Quotations and work orders of a customer. They belong to other modules, which will provide
    them through their inbound ports; until then the adapter returns an empty history."""

    @abstractmethod
    def history_for(self, customer_id: UUID, page_request: PageRequest) -> Page[HistoryEntry]: ...
