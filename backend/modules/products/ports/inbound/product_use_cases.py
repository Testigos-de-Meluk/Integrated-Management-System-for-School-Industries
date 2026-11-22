"""Inbound port of the Products module: what the outside world can ask for (US 2.1 … US 2.6).

Everything that crosses this boundary is a DTO made of plain values (``str``, ``UUID``,
``bool``). Domain entities never leave the application layer: callers receive a
:class:`ProductView`, so the domain can change without breaking the REST API or any other adapter.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from modules.products.domain.product import (
    CODE_MAX_LENGTH,
    NAME_MAX_LENGTH,
    UNIT_MAX_LENGTH,
    ProductStatus,
)
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor

#: Published for adapters (serializers, forms), so they validate the same limits as the domain
#: without importing it.
PRODUCT_STATUSES: tuple[str, ...] = tuple(status.value for status in ProductStatus)
__all__ = [
    "CODE_MAX_LENGTH",
    "NAME_MAX_LENGTH",
    "PRODUCT_STATUSES",
    "UNIT_MAX_LENGTH",
    "ProductFilters",
    "ProductUseCases",
    "ProductView",
    "RegisterProductCommand",
    "UpdateProductCommand",
]

# --- Input DTOs -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProductFilters:
    """All filters are optional and combined with AND (US 2.2.4).

    ``status`` is ``"ACTIVE"`` or ``"INACTIVE"``.
    """

    code: str | None = None
    name: str | None = None
    unit_of_measure: str | None = None
    #: Free search over code OR name (used by the public catalog).
    text: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class RegisterProductCommand:
    code: str
    name: str
    unit_of_measure: str


@dataclass(frozen=True, slots=True)
class UpdateProductCommand:
    name: str
    unit_of_measure: str


# --- Output DTO -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProductView:
    """Read-only representation of a product returned by every use case."""

    id: UUID
    code: str
    name: str
    unit_of_measure: str
    status: str  # "ACTIVE" | "INACTIVE"
    is_selectable: bool  # can be added to new quotations and work orders (FR-02-04)


# --- Port -------------------------------------------------------------------------------------


class ProductUseCases(ABC):
    @abstractmethod
    def list_products(
        self, actor: Actor, filters: ProductFilters, page_request: PageRequest
    ) -> Page[ProductView]: ...

    @abstractmethod
    def get_product(self, actor: Actor, product_id: UUID) -> ProductView: ...

    @abstractmethod
    def register_product(self, actor: Actor, command: RegisterProductCommand) -> ProductView: ...

    @abstractmethod
    def update_product(
        self, actor: Actor, product_id: UUID, command: UpdateProductCommand
    ) -> ProductView: ...

    @abstractmethod
    def activate_product(self, actor: Actor, product_id: UUID) -> ProductView: ...

    @abstractmethod
    def deactivate_product(self, actor: Actor, product_id: UUID) -> ProductView: ...
