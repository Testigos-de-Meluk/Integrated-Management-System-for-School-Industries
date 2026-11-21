"""Use cases of the Products module (implements the ``ProductUseCases`` inbound port).

Each use case follows the same steps:
1. check the actor's permission (deny by default);
2. load or create the aggregate and let the domain apply the business rules;
3. persist through the repository port;
4. write the audit record through the audit port;
5. return an output DTO (``ProductView``), never the entity.
"""

from uuid import UUID

from modules.products.domain.exceptions import DuplicateProductCode, ProductNotFound
from modules.products.domain.product import Product, normalize_code
from modules.products.ports.inbound.product_use_cases import (
    ProductFilters,
    ProductUseCases,
    ProductView,
    RegisterProductCommand,
    UpdateProductCommand,
)
from modules.products.ports.outbound.product_repository import ProductRepository
from modules.shared_kernel.domain.audit import AuditAction, AuditRecord
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, Permission
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger

ENTITY_TYPE = "Product"


def to_view(product: Product) -> ProductView:
    """Entity -> output DTO. The only place that knows both shapes."""
    return ProductView(
        id=product.id,
        code=product.code,
        name=product.name,
        unit_of_measure=product.unit_of_measure,
        status=product.status.value,
        is_selectable=product.is_selectable,
    )


class ProductService(ProductUseCases):
    def __init__(self, repository: ProductRepository, audit_logger: AuditLogger) -> None:
        self._repository = repository
        self._audit = audit_logger

    # --- Queries (Operador, Administrador, Superadministrador) --------------------------------

    def list_products(
        self, actor: Actor, filters: ProductFilters, page_request: PageRequest
    ) -> Page[ProductView]:
        actor.require(Permission.CATALOG_VIEW)
        page = self._repository.search(filters, page_request)
        return Page(items=[to_view(p) for p in page.items], total=page.total, request=page.request)

    def get_product(self, actor: Actor, product_id: UUID) -> ProductView:
        actor.require(Permission.CATALOG_VIEW)
        return to_view(self._get_or_fail(product_id))

    # --- Commands (Administrador, Superadministrador) -----------------------------------------

    def register_product(self, actor: Actor, command: RegisterProductCommand) -> ProductView:
        actor.require(Permission.CATALOG_EDIT)
        if self._repository.exists_with_code(normalize_code(command.code)):
            raise DuplicateProductCode()
        product = Product.register(command.code, command.name, command.unit_of_measure)
        self._repository.add(product)
        self._log(AuditAction.CREATED, actor, product, old=None)
        return to_view(product)

    def update_product(
        self, actor: Actor, product_id: UUID, command: UpdateProductCommand
    ) -> ProductView:
        actor.require(Permission.CATALOG_EDIT)
        product = self._get_or_fail(product_id)
        before = product.snapshot()
        product.update_details(command.name, command.unit_of_measure)
        self._repository.update(product)
        self._log(AuditAction.UPDATED, actor, product, old=before)
        return to_view(product)

    def activate_product(self, actor: Actor, product_id: UUID) -> ProductView:
        return self._change_status(actor, product_id, activate=True)

    def deactivate_product(self, actor: Actor, product_id: UUID) -> ProductView:
        return self._change_status(actor, product_id, activate=False)

    # --- Helpers ------------------------------------------------------------------------------

    def _change_status(self, actor: Actor, product_id: UUID, *, activate: bool) -> ProductView:
        actor.require(Permission.CATALOG_EDIT)
        product = self._get_or_fail(product_id)
        before = product.snapshot()
        if activate:
            product.activate()
        else:
            product.deactivate()
        self._repository.update(product)
        self._log(AuditAction.STATUS_CHANGED, actor, product, old=before)
        return to_view(product)

    def _get_or_fail(self, product_id: UUID) -> Product:
        product = self._repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFound()
        return product

    def _log(self, action: AuditAction, actor: Actor, product: Product, old: dict | None) -> None:
        self._audit.log(
            AuditRecord(
                action=action,
                entity_type=ENTITY_TYPE,
                entity_id=str(product.id),
                actor=actor,
                old_values=old,
                new_values=product.snapshot(),
            )
        )
