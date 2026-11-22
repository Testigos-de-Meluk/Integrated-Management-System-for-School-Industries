"""Inbound port used by OTHER MODULES and the public assistant: the selectable catalog.

No ``Actor`` and no permissions: it only exposes ACTIVE products (FR-02-04) and never prices
(RN-M2-01), so it is safe for the public portal.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest


@dataclass(frozen=True, slots=True)
class CatalogItem:
    id: UUID
    code: str
    name: str
    unit_of_measure: str


class ProductCatalog(ABC):
    @abstractmethod
    def search_selectable(self, text: str | None, page_request: PageRequest) -> Page[CatalogItem]:
        """Active products whose code or name contains ``text``, ordered by name."""

    @abstractmethod
    def all_selectable(self, limit: int = 500) -> list[CatalogItem]:
        """Every active product (up to ``limit``), ordered by name: e.g. for the AI assistant."""

    @abstractmethod
    def selectable_by_ids(self, product_ids: list[UUID]) -> dict[UUID, CatalogItem]:
        """Active products among ``product_ids`` (inactive or unknown ids are left out)."""
