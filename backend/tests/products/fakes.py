"""In-memory test doubles for the outbound ports: use cases are tested without a database."""

from uuid import UUID

from modules.products.domain.exceptions import DuplicateProductCode
from modules.products.domain.product import Product
from modules.products.ports.inbound.product_use_cases import ProductFilters
from modules.products.ports.outbound.product_repository import ProductRepository
from modules.shared_kernel.domain.audit import AuditRecord
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger


class InMemoryProductRepository(ProductRepository):
    def __init__(self) -> None:
        self.products: dict[UUID, Product] = {}

    def get_by_id(self, product_id: UUID) -> Product | None:
        return self.products.get(product_id)

    def exists_with_code(self, code: str) -> bool:
        return any(p.code == code for p in self.products.values())

    def add(self, product: Product) -> None:
        if self.exists_with_code(product.code):
            raise DuplicateProductCode()
        self.products[product.id] = product

    def update(self, product: Product) -> None:
        self.products[product.id] = product

    def search(self, filters: ProductFilters, page_request: PageRequest) -> Page[Product]:
        items = sorted(self.products.values(), key=lambda p: p.code)
        if filters.code:
            items = [p for p in items if filters.code.lower() in p.code.lower()]
        if filters.name:
            items = [p for p in items if filters.name.lower() in p.name.lower()]
        if filters.unit_of_measure:
            items = [p for p in items if p.unit_of_measure == filters.unit_of_measure]
        if filters.status:
            items = [p for p in items if p.status.value == filters.status]
        start = page_request.offset
        return Page(items[start : start + page_request.size], len(items), page_request)


class SpyAuditLogger(AuditLogger):
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def log(self, record: AuditRecord) -> None:
        self.records.append(record)
