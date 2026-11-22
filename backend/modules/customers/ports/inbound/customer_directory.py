"""Inbound port used by OTHER MODULES: look up registered customers (quotations, work orders).

No ``Actor``: the calling module has already checked its own permission.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CustomerSummary:
    id: UUID
    tax_id: str
    name: str
    is_active: bool


class CustomerDirectory(ABC):
    @abstractmethod
    def by_id(self, customer_id: UUID) -> CustomerSummary | None: ...

    @abstractmethod
    def by_tax_id(self, tax_id: str) -> CustomerSummary | None:
        """Accepts the NIT / document as typed (dots, spaces, with or without check digit)."""
