"""PostgreSQL adapters of the Customers module."""

from uuid import UUID

from django.db import IntegrityError, transaction

from modules.customers.domain.commercial_note import CommercialNote
from modules.customers.domain.customer import (
    Customer,
    CustomerStatus,
    CustomerType,
    customer_class,
)
from modules.customers.domain.exceptions import DuplicateTaxId
from modules.customers.domain.tax_id import search_key
from modules.customers.infrastructure.models import CommercialNoteModel, CustomerModel
from modules.customers.ports.inbound.customer_use_cases import CustomerFilters
from modules.customers.ports.outbound.repositories import (
    CustomerRepository,
    NoteRepository,
)
from modules.shared_kernel.domain.pagination import Page, PageRequest

_CUSTOMER_FIELDS = (
    "tax_id",
    "name",
    "address",
    "primary_phone",
    "email",
    "commercial_contact",
)


def _customer_to_domain(model: CustomerModel) -> Customer:
    subclass = customer_class(CustomerType(model.customer_type))
    return subclass(
        id=model.id,
        status=CustomerStatus(model.status),
        **{name: getattr(model, name) for name in _CUSTOMER_FIELDS},
    )


def _apply_customer(customer: Customer, model: CustomerModel) -> CustomerModel:
    model.id = customer.id
    model.customer_type = customer.customer_type.value
    model.status = customer.status.value
    for name in _CUSTOMER_FIELDS:
        setattr(model, name, getattr(customer, name))
    return model


class DjangoCustomerRepository(CustomerRepository):
    def get_by_id(self, customer_id: UUID) -> Customer | None:
        model = CustomerModel.objects.filter(pk=customer_id).first()
        return _customer_to_domain(model) if model else None

    def get_by_tax_id(self, tax_id: str) -> Customer | None:
        model = CustomerModel.objects.filter(tax_id=tax_id).first()
        return _customer_to_domain(model) if model else None

    def add(self, customer: Customer) -> None:
        try:
            with transaction.atomic():
                _apply_customer(customer, CustomerModel()).save(force_insert=True)
        except IntegrityError as error:
            raise DuplicateTaxId() from error

    def update(self, customer: Customer) -> None:
        _apply_customer(customer, CustomerModel.objects.get(pk=customer.id)).save()

    def search(self, filters: CustomerFilters, page_request: PageRequest) -> Page[Customer]:
        queryset = CustomerModel.objects.all()
        if filters.tax_id:
            queryset = queryset.filter(tax_id__icontains=search_key(filters.tax_id))
        if filters.name:
            queryset = queryset.filter(name__icontains=filters.name.strip())
        if filters.commercial_contact:
            queryset = queryset.filter(
                commercial_contact__icontains=filters.commercial_contact.strip()
            )
        if filters.status:
            queryset = queryset.filter(status=filters.status)

        total = queryset.count()
        start = page_request.offset
        models = queryset.order_by("name", "tax_id")[start : start + page_request.size]
        return Page([_customer_to_domain(m) for m in models], total, page_request)


def _note_to_domain(model: CommercialNoteModel) -> CommercialNote:
    return CommercialNote(
        id=model.id,
        customer_id=model.customer_id,
        content=model.content,
        author_id=model.author_id,
        author_name=model.author_name,
        created_at=model.created_at,
        updated_at=model.updated_at,
        updated_by_id=model.updated_by_id,
        updated_by_name=model.updated_by_name,
    )


class DjangoNoteRepository(NoteRepository):
    def get(self, note_id: UUID) -> CommercialNote | None:
        model = CommercialNoteModel.objects.filter(pk=note_id).first()
        return _note_to_domain(model) if model else None

    def add(self, note: CommercialNote) -> None:
        CommercialNoteModel.objects.create(
            id=note.id,
            customer_id=note.customer_id,
            content=note.content,
            author_id=note.author_id,
            author_name=note.author_name,
            created_at=note.created_at,
        )

    def update(self, note: CommercialNote) -> None:
        CommercialNoteModel.objects.filter(pk=note.id).update(
            content=note.content,
            updated_at=note.updated_at,
            updated_by_id=note.updated_by_id,
            updated_by_name=note.updated_by_name,
        )

    def delete(self, note_id: UUID) -> None:
        CommercialNoteModel.objects.filter(pk=note_id).delete()

    def list_for_customer(
        self, customer_id: UUID, page_request: PageRequest
    ) -> Page[CommercialNote]:
        queryset = CommercialNoteModel.objects.filter(customer_id=customer_id)
        total = queryset.count()
        start = page_request.offset
        models = queryset.order_by("-created_at")[start : start + page_request.size]
        return Page([_note_to_domain(m) for m in models], total, page_request)
