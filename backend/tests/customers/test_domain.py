"""Pure domain tests for customers and commercial notes (no database)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from modules.customers.domain.commercial_note import CommercialNote
from modules.customers.domain.customer import (
    Customer,
    CustomerType,
    LegalEntity,
    NaturalPerson,
)
from modules.customers.domain.exceptions import (
    CustomerReadOnly,
    InvalidCustomerStatusChange,
    NoteEditNotAllowed,
)
from modules.customers.domain.tax_id import nit_check_digit, normalize_nit
from modules.shared_kernel.domain.exceptions import ValidationError

NOW = datetime.now(UTC)
CONTACT = {
    "address": "Carrera 18 # 126-40, Bogotá",
    "primary_phone": "310 456 7890",
    "email": "Compras@ColegioLosRobles.edu.co",
}


def legal(tax_id="800197268-4", **overrides):
    return Customer.register(
        CustomerType.LEGAL_ENTITY, tax_id, "Colegio Los Robles SAS", **(CONTACT | overrides)
    )


def test_dian_check_digit():
    assert nit_check_digit("800197268") == 4  # NIT of the DIAN itself
    assert nit_check_digit("900456789") in range(10)


@pytest.mark.parametrize("raw", ["800197268-4", "800.197.268-4", "8001972684", " 800 197 268-4 "])
def test_nit_is_normalized_from_common_formats(raw):
    assert normalize_nit(raw) == ("800197268-4", None)


@pytest.mark.parametrize(
    "raw, message",
    [
        ("800197268-5", "El dígito de verificación del NIT no es válido."),
        ("80019726-4", "Ingrese el NIT con su dígito de verificación (por ejemplo, 900456789-1)."),
        ("ABC", "Ingrese el NIT con su dígito de verificación (por ejemplo, 900456789-1)."),
    ],
)
def test_invalid_nits(raw, message):
    assert normalize_nit(raw) == (None, message)


def test_factory_creates_the_right_subclass():
    company = legal()
    person = Customer.register(
        CustomerType.NATURAL_PERSON, "1.020.304.050", "Laura Méndez", **CONTACT
    )

    assert isinstance(company, LegalEntity) and company.tax_id == "800197268-4"
    assert isinstance(person, NaturalPerson) and person.tax_id == "1020304050"
    assert company.email == "compras@colegiolosrobles.edu.co"
    assert company.is_active


def test_register_reports_all_invalid_fields_at_once():
    with pytest.raises(ValidationError) as error:
        Customer.register(CustomerType.LEGAL_ENTITY, "123", "", "", "abc", "no-email")

    assert set(error.value.errors) == {"tax_id", "name", "address", "primary_phone", "email"}


def test_update_keeps_type_and_tax_id_and_inactive_is_read_only():
    customer = legal()
    customer.update_details("Colegio Los Robles", "Calle 1", "601 555 1234", "a@b.co", "Laura")

    assert (customer.tax_id, customer.commercial_contact) == ("800197268-4", "Laura")

    customer.deactivate()
    with pytest.raises(CustomerReadOnly):
        customer.update_details("X", "Calle 1", "601 555 1234", "a@b.co", None)
    with pytest.raises(InvalidCustomerStatusChange):
        customer.deactivate()
    customer.activate()
    assert customer.is_active


def test_note_only_editable_by_its_author_and_keeps_original_data():
    author, other = uuid4(), uuid4()
    note = CommercialNote.write(uuid4(), "  Coordinar despacho  ", author, "Marta Ruiz", NOW)

    assert note.content == "Coordinar despacho" and not note.is_edited
    with pytest.raises(NoteEditNotAllowed):
        note.edit("Otro texto", other, "Ana", NOW)

    note.edit("Despacho el lunes", author, "Marta Ruiz", NOW)
    assert note.is_edited and note.author_name == "Marta Ruiz" and note.created_at == NOW


def test_empty_note_is_rejected():
    with pytest.raises(ValidationError) as error:
        CommercialNote.write(uuid4(), "   ", uuid4(), "Marta", NOW)

    assert error.value.errors == {"content": ["La nota no puede estar vacía."]}
