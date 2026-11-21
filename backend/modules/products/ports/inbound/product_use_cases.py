"""Inbound port of the Products module: what the outside world can ask for (US 2.1 … US 2.6)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from modules.products.domain.product import Product, ProductStatus
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor


@dataclass(frozen=True, slots=True)
class ProductFilters:
    """All filters are optional and combined with AND (US 2.2.4)."""

    code: str | None = None
    name: str | None = None
    unit_of_measure: str | None = None
    status: ProductStatus | None = None


@dataclass(frozen=True, slots=True)
class RegisterProductCommand:
    code: str
    name: str
    unit_of_measure: str


@dataclass(frozen=True, slots=True)
class UpdateProductCommand:
    name: str
    unit_of_measure: str


class ProductUseCases(ABC):
    @abstractmethod
    def list_products(
        self, actor: Actor, filters: ProductFilters, page_request: PageRequest
    ) -> Page[Product]: ...

    @abstractmethod
    def get_product(self, actor: Actor, product_id: UUID) -> Product: ...

    @abstractmethod
    def register_product(self, actor: Actor, command: RegisterProductCommand) -> Product: ...

    @abstractmethod
    def update_product(
        self, actor: Actor, product_id: UUID, command: UpdateProductCommand
    ) -> Product: ...

    @abstractmethod
    def activate_product(self, actor: Actor, product_id: UUID) -> Product: ...

    @abstractmethod
    def deactivate_product(self, actor: Actor, product_id: UUID) -> Product: ...
