"""Outbound port of the Products module: how products are stored, whatever the technology."""

from abc import ABC, abstractmethod
from uuid import UUID

from modules.products.domain.product import Product
from modules.products.ports.inbound.product_use_cases import ProductFilters
from modules.shared_kernel.domain.pagination import Page, PageRequest


class ProductRepository(ABC):
    @abstractmethod
    def get_by_id(self, product_id: UUID) -> Product | None: ...

    @abstractmethod
    def exists_with_code(self, code: str) -> bool: ...

    @abstractmethod
    def add(self, product: Product) -> None:
        """Stores a new product. Raises ``DuplicateProductCode`` if the code already exists."""

    @abstractmethod
    def update(self, product: Product) -> None: ...

    @abstractmethod
    def search(self, filters: ProductFilters, page_request: PageRequest) -> Page[Product]:
        """Returns one page of products matching every filter, ordered by code."""
