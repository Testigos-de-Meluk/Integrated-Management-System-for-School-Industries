"""Composition root of the Customers module."""

from functools import lru_cache

from modules.customers.application.customer_directory_service import CustomerDirectoryService
from modules.customers.application.customer_service import CustomerService
from modules.customers.ports.inbound.customer_directory import CustomerDirectory
from modules.customers.ports.inbound.customer_use_cases import CustomerUseCases
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger

from .persistence.history import QuotationsCommercialHistory
from .persistence.repositories import DjangoCustomerRepository, DjangoNoteRepository


@lru_cache(maxsize=1)
def customer_use_cases() -> CustomerUseCases:
    # Imported here: the quotations module also imports this module (customer directory).
    from modules.quotations.infrastructure.dependencies import customer_quotations

    return CustomerService(
        customers=DjangoCustomerRepository(),
        notes=DjangoNoteRepository(),
        # Quotations now; work orders join in step 5.
        history=QuotationsCommercialHistory(customer_quotations()),
        audit_logger=DatabaseAuditLogger(),
    )


@lru_cache(maxsize=1)
def customer_directory() -> CustomerDirectory:
    """For other modules: look up registered customers."""
    return CustomerDirectoryService(DjangoCustomerRepository())
