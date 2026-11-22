"""Composition root of the Products module: connects the use cases to their adapters.

This is the only place that knows which concrete adapters implement each port. To replace an
adapter, change it here; use cases stay untouched.
"""

from functools import lru_cache

from modules.products.application.product_catalog_service import ProductCatalogService
from modules.products.application.product_service import ProductService
from modules.products.ports.inbound.product_catalog import ProductCatalog
from modules.products.ports.inbound.product_use_cases import ProductUseCases
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger

from .persistence.django_product_repository import DjangoProductRepository


@lru_cache(maxsize=1)
def product_use_cases() -> ProductUseCases:
    """Single shared instance: the service is stateless."""
    return ProductService(repository=DjangoProductRepository(), audit_logger=DatabaseAuditLogger())


@lru_cache(maxsize=1)
def product_catalog() -> ProductCatalog:
    """Port for other modules and the public assistant: active products, no prices."""
    return ProductCatalogService(DjangoProductRepository())
