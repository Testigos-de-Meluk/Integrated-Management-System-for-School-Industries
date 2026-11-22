"""Implements the ``ProductCatalog`` port (selectable products, no prices, no permissions)."""

from uuid import UUID

from modules.products.domain.product import Product, ProductStatus
from modules.products.ports.inbound.product_catalog import CatalogItem, ProductCatalog
from modules.products.ports.inbound.product_use_cases import ProductFilters
from modules.products.ports.outbound.product_repository import ProductRepository
from modules.shared_kernel.domain.pagination import Page, PageRequest


def to_item(product: Product) -> CatalogItem:
    return CatalogItem(product.id, product.code, product.name, product.unit_of_measure)


class ProductCatalogService(ProductCatalog):
    def __init__(self, repository: ProductRepository) -> None:
        self._repository = repository

    def search_selectable(self, text: str | None, page_request: PageRequest) -> Page[CatalogItem]:
        filters = ProductFilters(text=(text or "").strip() or None, status=ProductStatus.ACTIVE)
        page = self._repository.search(filters, page_request)
        return Page([to_item(p) for p in page.items], page.total, page.request)

    def selectable_by_ids(self, product_ids: list[UUID]) -> dict[UUID, CatalogItem]:
        result: dict[UUID, CatalogItem] = {}
        for product_id in set(product_ids):
            product = self._repository.get_by_id(product_id)
            if product is not None and product.is_selectable:
                result[product.id] = to_item(product)
        return result
