"""Inbound port of the Customers module (FR-02-07 … FR-02-11; US 2.14 … US 2.24).

Only DTOs with plain values cross this boundary.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from modules.customers.domain.commercial_note import CONTENT_MAX_LENGTH as NOTE_MAX_LENGTH
from modules.customers.domain.customer import (
    ADDRESS_MAX_LENGTH,
    CONTACT_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    NAME_MAX_LENGTH,
    PHONE_MAX_LENGTH,
    CustomerStatus,
    CustomerType,
)
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor

#: Published for adapters, so they validate the same limits as the domain without importing it.
CUSTOMER_TYPES: tuple[str, ...] = tuple(t.value for t in CustomerType)
CUSTOMER_STATUSES: tuple[str, ...] = tuple(s.value for s in CustomerStatus)
__all__ = [
    "ADDRESS_MAX_LENGTH",
    "CONTACT_MAX_LENGTH",
    "CUSTOMER_STATUSES",
    "CUSTOMER_TYPES",
    "EMAIL_MAX_LENGTH",
    "NAME_MAX_LENGTH",
    "NOTE_MAX_LENGTH",
    "PHONE_MAX_LENGTH",
    "CustomerFilters",
    "CustomerUseCases",
    "CustomerView",
    "HistoryEntryView",
    "NoteView",
    "RegisterCustomerCommand",
    "UpdateCustomerCommand",
]

# --- Input DTOs -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CustomerFilters:
    """All optional, combined with AND (US 2.15)."""

    tax_id: str | None = None
    name: str | None = None
    commercial_contact: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class RegisterCustomerCommand:
    customer_type: str  # "NATURAL_PERSON" | "LEGAL_ENTITY"
    tax_id: str
    name: str
    address: str
    primary_phone: str
    email: str
    commercial_contact: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateCustomerCommand:
    """Type and NIT/document are not here: they can never change (FR-02-10)."""

    name: str
    address: str
    primary_phone: str
    email: str
    commercial_contact: str | None = None


# --- Output DTOs ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CustomerView:
    id: UUID
    customer_type: str
    tax_id: str
    name: str
    address: str
    primary_phone: str
    email: str
    commercial_contact: str
    status: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class HistoryEntryView:
    """One quotation or work order of the customer (US 2.20)."""

    document_type: str  # "QUOTATION" | "WORK_ORDER"
    reference: str
    date: datetime
    status: str


@dataclass(frozen=True, slots=True)
class NoteView:
    id: UUID
    content: str
    author_name: str
    created_at: datetime
    is_edited: bool
    updated_at: datetime | None
    updated_by_name: str
    can_edit: bool  # the current user wrote it


# --- Port -------------------------------------------------------------------------------------


class CustomerUseCases(ABC):
    @abstractmethod
    def list_customers(
        self, actor: Actor, filters: CustomerFilters, page_request: PageRequest
    ) -> Page[CustomerView]: ...

    @abstractmethod
    def get_customer(self, actor: Actor, customer_id: UUID) -> CustomerView: ...

    @abstractmethod
    def get_customer_by_tax_id(self, actor: Actor, tax_id: str) -> CustomerView:
        """The unified profile is identified by NIT / document number (FR-02-08)."""

    @abstractmethod
    def register_customer(self, actor: Actor, command: RegisterCustomerCommand) -> CustomerView: ...

    @abstractmethod
    def update_customer(
        self, actor: Actor, customer_id: UUID, command: UpdateCustomerCommand
    ) -> CustomerView: ...

    @abstractmethod
    def deactivate_customer(self, actor: Actor, customer_id: UUID) -> CustomerView: ...

    @abstractmethod
    def activate_customer(self, actor: Actor, customer_id: UUID) -> CustomerView: ...

    @abstractmethod
    def customer_history(
        self, actor: Actor, customer_id: UUID, page_request: PageRequest
    ) -> Page[HistoryEntryView]:
        """Quotations and work orders, newest first (US 2.20)."""

    @abstractmethod
    def list_notes(
        self, actor: Actor, customer_id: UUID, page_request: PageRequest
    ) -> Page[NoteView]:
        """Newest first (US 2.21)."""

    @abstractmethod
    def add_note(self, actor: Actor, customer_id: UUID, content: str) -> NoteView: ...

    @abstractmethod
    def edit_note(
        self, actor: Actor, customer_id: UUID, note_id: UUID, content: str
    ) -> NoteView: ...

    @abstractmethod
    def delete_note(self, actor: Actor, customer_id: UUID, note_id: UUID) -> None:
        """Any user with permission can delete a note; its text is kept in the audit log."""
