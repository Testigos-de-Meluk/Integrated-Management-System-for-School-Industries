"""Composition root of the Customers module."""

from functools import lru_cache

from modules.customers.application.customer_service import CustomerService
from modules.customers.ports.inbound.customer_use_cases import CustomerUseCases
from modules.shared_kernel.infrastructure.audit.database_audit_logger import DatabaseAuditLogger

from .persistence.repositories import (
    DjangoCustomerRepository,
    DjangoNoteRepository,
    EmptyCommercialHistory,
)


@lru_cache(maxsize=1)
def customer_use_cases() -> CustomerUseCases:
    return CustomerService(
        customers=DjangoCustomerRepository(),
        notes=DjangoNoteRepository(),
        history=EmptyCommercialHistory(),  # replaced when quotations / work orders exist
        audit_logger=DatabaseAuditLogger(),
    )
