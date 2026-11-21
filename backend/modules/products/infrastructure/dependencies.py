"""Composition root of the Products module: connects the use cases to their adapters.

This is the only place that knows which concrete adapters implement each port. To replace an
adapter (for example the temporary audit logger), change it here; use cases stay untouched.
"""

from functools import lru_cache

from modules.products.application.product_service import ProductService
from modules.products.ports.inbound.product_use_cases import ProductUseCases
from modules.shared_kernel.infrastructure.audit.logging_audit_logger import LoggingAuditLogger

from .persistence.django_product_repository import DjangoProductRepository


@lru_cache(maxsize=1)
def product_use_cases() -> ProductUseCases:
    """Single shared instance: the service is stateless."""
    return ProductService(repository=DjangoProductRepository(), audit_logger=LoggingAuditLogger())
