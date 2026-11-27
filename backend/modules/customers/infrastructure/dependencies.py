"""Composition root of the Customers module."""

from functools import lru_cache

from modules.customers.application.customer_directory_service import CustomerDirectoryService
from modules.customers.application.customer_service import CustomerService
from modules.customers.ports.inbound.customer_directory import CustomerDirectory
from modules.customers.ports.inbound.customer_use_cases import CustomerUseCases
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger

from .persistence.history import ModulesCommercialHistory
from .persistence.repositories import DjangoCustomerRepository, DjangoNoteRepository


@lru_cache(maxsize=1)
def customer_use_cases() -> CustomerUseCases:
    # Imported here: the quotations and work orders modules also import this module.
    from modules.quotations.infrastructure.dependencies import customer_quotations
    from modules.work_orders.infrastructure.dependencies import customer_work_orders

    return CustomerService(
        customers=DjangoCustomerRepository(),
        notes=DjangoNoteRepository(),
        history=ModulesCommercialHistory(customer_quotations(), customer_work_orders()),
        audit_logger=DatabaseAuditLogger(),
    )


@lru_cache(maxsize=1)
def customer_directory() -> CustomerDirectory:
    """For other modules: look up registered customers."""
    return CustomerDirectoryService(DjangoCustomerRepository())
