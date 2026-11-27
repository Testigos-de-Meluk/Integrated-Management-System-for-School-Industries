"""Customer use cases with in-memory adapters (no database)."""

from uuid import UUID, uuid4

import pytest

from modules.customers.application.customer_service import CustomerService
from modules.customers.domain.commercial_note import CommercialNote
from modules.customers.domain.customer import Customer
from modules.customers.domain.exceptions import CustomerNotFound, DuplicateTaxId
from modules.customers.ports.inbound.customer_use_cases import (
    CustomerFilters,
    RegisterCustomerCommand,
)
from modules.customers.ports.outbound.repositories import (
    CommercialHistoryProvider,
    CustomerRepository,
    NoteRepository,
)
from modules.shared_kernel.domain.audit import AuditAction
from modules.shared_kernel.domain.exceptions import PermissionDeniedError
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, Permission, RoleType

from ..shared_fakes import SpyAuditLogger

OPERATOR = Actor.for_role(RoleType.OPERATOR, user_id=uuid4(), display_name="Marta Ruiz")


class InMemoryCustomers(CustomerRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, Customer] = {}

    def get_by_id(self, customer_id):
        return self.items.get(customer_id)

    def get_by_tax_id(self, tax_id):
        return next((c for c in self.items.values() if c.tax_id == tax_id), None)

    def add(self, customer):
        self.items[customer.id] = customer

    def update(self, customer):
        self.items[customer.id] = customer

    def search(self, filters: CustomerFilters, page_request: PageRequest):
        items = sorted(self.items.values(), key=lambda c: c.name)
        return Page(items, len(items), page_request)


class InMemoryNotes(NoteRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, CommercialNote] = {}

    def get(self, note_id):
        return self.items.get(note_id)

    def add(self, note):
        self.items[note.id] = note

    def update(self, note):
        self.items[note.id] = note

    def delete(self, note_id):
        self.items.pop(note_id, None)

    def list_for_customer(self, customer_id, page_request):
        items = [n for n in self.items.values() if n.customer_id == customer_id]
        return Page(items, len(items), page_request)


@pytest.fixture
def audit():
    return SpyAuditLogger()


class EmptyHistory(CommercialHistoryProvider):
    def history_for(self, customer_id, document_type, page_request):
        return Page([], 0, page_request)


@pytest.fixture
def service(audit):
    return CustomerService(InMemoryCustomers(), InMemoryNotes(), EmptyHistory(), audit)


def register(service, actor=OPERATOR, tax_id="800197268-4"):
    command = RegisterCustomerCommand(
        "LEGAL_ENTITY", tax_id, "Colegio Los Robles", "Calle 1", "6015551234", "a@b.co"
    )
    return service.register_customer(actor, command)


def test_register_audits_and_rejects_duplicates(service, audit):
    view = register(service)

    assert view.tax_id == "800197268-4"
    assert audit.records[-1].action is AuditAction.CREATED
    with pytest.raises(DuplicateTaxId):
        register(service, tax_id="800.197.268-4")


def test_actor_without_customer_permission_is_denied(service):
    nobody = Actor(role=RoleType.OPERATOR, permissions=frozenset({Permission.CATALOG_VIEW}))

    with pytest.raises(PermissionDeniedError):
        register(service, actor=nobody)


def test_profile_lookup_accepts_any_tax_id_format(service):
    view = register(service)

    assert service.get_customer_by_tax_id(OPERATOR, "8001972684").id == view.id
    with pytest.raises(CustomerNotFound):
        service.get_customer_by_tax_id(OPERATOR, "123")


def test_notes_are_signed_with_the_actor_name_and_deletion_keeps_the_text(service, audit):
    customer = register(service)

    note = service.add_note(OPERATOR, customer.id, "Llamar el lunes")
    service.delete_note(OPERATOR, customer.id, note.id)

    assert note.author_name == "Marta Ruiz" and note.can_edit
    assert audit.records[-1].action is AuditAction.DELETED
    assert audit.records[-1].old_values["content"] == "Llamar el lunes"
