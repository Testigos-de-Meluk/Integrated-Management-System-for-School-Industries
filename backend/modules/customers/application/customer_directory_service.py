"""Implements ``CustomerDirectory`` for other modules (quotations now, work orders in step 5)."""

from uuid import UUID

from modules.customers.domain.customer import Customer, CustomerType, customer_class
from modules.customers.domain.tax_id import NIT_DIGITS, nit_check_digit, search_key
from modules.customers.ports.inbound.customer_directory import CustomerDirectory, CustomerSummary
from modules.customers.ports.outbound.repositories import CustomerRepository


def find_by_any_tax_id_format(customers: CustomerRepository, raw: str) -> Customer | None:
    """Accepts the id as typed (with dots, without hyphen…) for either customer type."""
    for customer_type in CustomerType:
        normalized, _ = customer_class(customer_type).normalize_tax_id(raw)
        if normalized and (customer := customers.get_by_tax_id(normalized)):
            return customer
    return None


def _summary(customer: Customer) -> CustomerSummary:
    return CustomerSummary(customer.id, customer.tax_id, customer.name, customer.is_active)


class CustomerDirectoryService(CustomerDirectory):
    def __init__(self, customers: CustomerRepository) -> None:
        self._customers = customers

    def by_id(self, customer_id: UUID) -> CustomerSummary | None:
        customer = self._customers.get_by_id(customer_id)
        return _summary(customer) if customer else None

    def by_tax_id(self, tax_id: str) -> CustomerSummary | None:
        customer = find_by_any_tax_id_format(self._customers, tax_id)
        digits = search_key(tax_id)
        if customer is None and digits.isdigit() and len(digits) == NIT_DIGITS:
            # A NIT typed without its check digit (common in the public form).
            customer = self._customers.get_by_tax_id(f"{digits}-{nit_check_digit(digits)}")
        return _summary(customer) if customer else None
