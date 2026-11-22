"""Use cases of the Customers module (implements ``CustomerUseCases``).

Every use case requires ``CUSTOMER_MANAGE`` (Operador, Administrador, Superadministrador).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.customers.application.customer_directory_service import find_by_any_tax_id_format
from modules.customers.domain.commercial_note import CommercialNote
from modules.customers.domain.customer import Customer, CustomerType
from modules.customers.domain.exceptions import CustomerNotFound, DuplicateTaxId, NoteNotFound
from modules.customers.ports.inbound.customer_use_cases import (
    CustomerFilters,
    CustomerUseCases,
    CustomerView,
    HistoryEntryView,
    NoteView,
    RegisterCustomerCommand,
    UpdateCustomerCommand,
)
from modules.customers.ports.outbound.repositories import (
    CommercialHistoryProvider,
    CustomerRepository,
    NoteRepository,
)
from modules.shared_kernel.domain.audit import AuditAction, AuditRecord
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, Permission
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger


def to_view(customer: Customer) -> CustomerView:
    return CustomerView(
        id=customer.id,
        customer_type=customer.customer_type.value,
        tax_id=customer.tax_id,
        name=customer.name,
        address=customer.address,
        primary_phone=customer.primary_phone,
        email=customer.email,
        commercial_contact=customer.commercial_contact,
        status=customer.status.value,
        is_active=customer.is_active,
    )


def note_view(note: CommercialNote, actor: Actor) -> NoteView:
    return NoteView(
        id=note.id,
        content=note.content,
        author_name=note.author_name,
        created_at=note.created_at,
        is_edited=note.is_edited,
        updated_at=note.updated_at,
        updated_by_name=note.updated_by_name,
        can_edit=note.can_be_edited_by(actor.user_id),
    )


def parse_type(raw: str) -> CustomerType:
    try:
        return CustomerType(raw)
    except ValueError as error:
        raise ValidationError.for_field(
            "customer_type", "Seleccione el tipo de cliente: persona natural o jurídica."
        ) from error


class CustomerService(CustomerUseCases):
    def __init__(
        self,
        customers: CustomerRepository,
        notes: NoteRepository,
        history: CommercialHistoryProvider,
        audit_logger: AuditLogger,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._customers = customers
        self._notes = notes
        self._history = history
        self._audit = audit_logger
        self._now = clock

    # --- Customers: queries -------------------------------------------------------------------

    def list_customers(
        self, actor: Actor, filters: CustomerFilters, page_request: PageRequest
    ) -> Page[CustomerView]:
        actor.require(Permission.CUSTOMER_MANAGE)
        page = self._customers.search(filters, page_request)
        return Page([to_view(c) for c in page.items], page.total, page.request)

    def get_customer(self, actor: Actor, customer_id: UUID) -> CustomerView:
        actor.require(Permission.CUSTOMER_MANAGE)
        return to_view(self._get_or_fail(customer_id))

    def get_customer_by_tax_id(self, actor: Actor, tax_id: str) -> CustomerView:
        actor.require(Permission.CUSTOMER_MANAGE)
        customer = find_by_any_tax_id_format(self._customers, tax_id)
        if customer is None:
            raise CustomerNotFound()  # US 2.19.4
        return to_view(customer)

    # --- Customers: commands ------------------------------------------------------------------

    def register_customer(self, actor: Actor, command: RegisterCustomerCommand) -> CustomerView:
        actor.require(Permission.CUSTOMER_MANAGE)
        customer = Customer.register(
            parse_type(command.customer_type),
            command.tax_id,
            command.name,
            command.address,
            command.primary_phone,
            command.email,
            command.commercial_contact,
        )
        if self._customers.get_by_tax_id(customer.tax_id) is not None:
            raise DuplicateTaxId()
        self._customers.add(customer)
        self._log(AuditAction.CREATED, actor, customer, old=None)
        return to_view(customer)

    def update_customer(
        self, actor: Actor, customer_id: UUID, command: UpdateCustomerCommand
    ) -> CustomerView:
        actor.require(Permission.CUSTOMER_MANAGE)
        customer = self._get_or_fail(customer_id)
        before = customer.snapshot()
        customer.update_details(
            command.name,
            command.address,
            command.primary_phone,
            command.email,
            command.commercial_contact,
        )
        self._customers.update(customer)
        self._log(AuditAction.UPDATED, actor, customer, old=before)
        return to_view(customer)

    def deactivate_customer(self, actor: Actor, customer_id: UUID) -> CustomerView:
        return self._change_status(actor, customer_id, activate=False)

    def activate_customer(self, actor: Actor, customer_id: UUID) -> CustomerView:
        return self._change_status(actor, customer_id, activate=True)

    def customer_history(
        self, actor: Actor, customer_id: UUID, page_request: PageRequest
    ) -> Page[HistoryEntryView]:
        actor.require(Permission.CUSTOMER_MANAGE)
        self._get_or_fail(customer_id)
        page = self._history.history_for(customer_id, page_request)
        items = [
            HistoryEntryView(e.document_type, e.reference, e.date, e.status) for e in page.items
        ]
        return Page(items, page.total, page.request)

    # --- Commercial notes ---------------------------------------------------------------------

    def list_notes(
        self, actor: Actor, customer_id: UUID, page_request: PageRequest
    ) -> Page[NoteView]:
        actor.require(Permission.CUSTOMER_MANAGE)
        self._get_or_fail(customer_id)
        page = self._notes.list_for_customer(customer_id, page_request)
        return Page([note_view(n, actor) for n in page.items], page.total, page.request)

    def add_note(self, actor: Actor, customer_id: UUID, content: str) -> NoteView:
        actor.require(Permission.CUSTOMER_MANAGE)
        customer = self._get_or_fail(customer_id)
        customer.ensure_editable()  # US 2.22.4: inactive profile is read-only
        note = CommercialNote.write(
            customer.id, content, actor.user_id, self._author_name(actor), self._now()
        )
        self._notes.add(note)
        self._log_note(AuditAction.CREATED, actor, note, old=None, new={"content": note.content})
        return note_view(note, actor)

    def edit_note(self, actor: Actor, customer_id: UUID, note_id: UUID, content: str) -> NoteView:
        actor.require(Permission.CUSTOMER_MANAGE)
        customer = self._get_or_fail(customer_id)
        customer.ensure_editable()  # US 2.23.4
        note = self._get_note_or_fail(customer_id, note_id)
        before = note.content
        note.edit(content, actor.user_id, self._author_name(actor), self._now())
        self._notes.update(note)
        self._log_note(
            AuditAction.UPDATED, actor, note, old={"content": before}, new={"content": note.content}
        )
        return note_view(note, actor)

    def delete_note(self, actor: Actor, customer_id: UUID, note_id: UUID) -> None:
        actor.require(Permission.CUSTOMER_MANAGE)
        customer = self._get_or_fail(customer_id)
        customer.ensure_editable()  # US 2.24.5
        note = self._get_note_or_fail(customer_id, note_id)
        self._notes.delete(note.id)
        # US 2.24.4: the audit log keeps who deleted it, when, and the deleted text.
        self._log_note(
            AuditAction.DELETED,
            actor,
            note,
            old={"content": note.content, "author": note.author_name},
            new=None,
        )

    # --- Helpers ------------------------------------------------------------------------------

    def _change_status(self, actor: Actor, customer_id: UUID, *, activate: bool) -> CustomerView:
        actor.require(Permission.CUSTOMER_MANAGE)
        customer = self._get_or_fail(customer_id)
        before = customer.snapshot()
        if activate:
            customer.activate()
        else:
            customer.deactivate()
        self._customers.update(customer)
        self._log(AuditAction.STATUS_CHANGED, actor, customer, old=before)
        return to_view(customer)

    def _get_or_fail(self, customer_id: UUID) -> Customer:
        customer = self._customers.get_by_id(customer_id)
        if customer is None:
            raise CustomerNotFound()
        return customer

    def _get_note_or_fail(self, customer_id: UUID, note_id: UUID) -> CommercialNote:
        note = self._notes.get(note_id)
        if note is None or note.customer_id != customer_id:
            raise NoteNotFound()
        return note

    @staticmethod
    def _author_name(actor: Actor) -> str:
        return actor.display_name or actor.role.value

    def _log(self, action: AuditAction, actor: Actor, customer: Customer, old: dict | None) -> None:
        self._audit.log(
            AuditRecord(
                action=action,
                entity_type="Customer",
                entity_id=str(customer.id),
                actor=actor,
                old_values=old,
                new_values=customer.snapshot(),
            )
        )

    def _log_note(
        self,
        action: AuditAction,
        actor: Actor,
        note: CommercialNote,
        old: dict | None,
        new: dict | None,
    ) -> None:
        self._audit.log(
            AuditRecord(
                action=action,
                entity_type="CommercialNote",
                entity_id=str(note.id),
                actor=actor,
                old_values=old,
                new_values={**(new or {}), "customer_id": str(note.customer_id)},
            )
        )
