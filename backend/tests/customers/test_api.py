"""Customers and commercial notes through the REST API, with real sessions."""

import pytest

from modules.customers.domain.exceptions import DUPLICATE_TAX_ID_MESSAGE
from modules.shared_kernel.domain.security import RoleType
from modules.shared_kernel.infrastructure.models import AuditEntryModel

pytestmark = pytest.mark.django_db

URL = "/api/customers/"
COMPANY = {
    "customer_type": "LEGAL_ENTITY",
    "tax_id": "800.197.268-4",
    "name": "Colegio Los Robles SAS",
    "address": "Carrera 18 # 126-40, Bogotá",
    "primary_phone": "310 456 7890",
    "email": "compras@colegiolosrobles.edu.co",
    "commercial_contact": "Laura Méndez · 310 456 7890",
}


@pytest.fixture
def operator(logged_in_client):
    """Customers are managed by the Operador (FR-02-07)."""
    return logged_in_client(RoleType.OPERATOR)


def create(client, **overrides):
    return client.post(URL, COMPANY | overrides, format="json")


def test_operator_registers_finds_by_tax_id_and_edits_a_customer(operator):
    created = create(operator)
    assert created.status_code == 201
    body = created.json()
    assert body["tax_id"] == "800197268-4" and body["customer_type"] == "LEGAL_ENTITY"

    found = operator.get(f"{URL}by-tax-id/8001972684/")  # any common format
    assert found.status_code == 200 and found.json()["id"] == body["id"]

    edited = operator.patch(
        f"{URL}{body['id']}/",
        {**COMPANY, "name": "Colegio Los Robles", "tax_id": "900000000-0"},
        format="json",
    )
    assert edited.json()["name"] == "Colegio Los Robles"
    assert edited.json()["tax_id"] == "800197268-4"  # immutable (FR-02-10)


def test_duplicate_and_invalid_tax_ids(operator):
    create(operator)

    duplicate = create(operator, tax_id="8001972684")
    assert duplicate.status_code == 400
    assert duplicate.json()["errors"] == {"tax_id": [DUPLICATE_TAX_ID_MESSAGE]}

    wrong_dv = create(operator, tax_id="800197268-5")
    assert wrong_dv.json()["errors"]["tax_id"] == [
        "El dígito de verificación del NIT no es válido."
    ]


def test_unknown_tax_id_returns_404(operator):
    response = operator.get(f"{URL}by-tax-id/123456789/")

    assert response.status_code == 404 and response.json()["detail"] == "El cliente no existe."


def test_list_filters_by_tax_id_name_contact_and_status(operator):
    create(operator)
    create(
        operator,
        customer_type="NATURAL_PERSON",
        tax_id="1020304050",
        name="Andrés Pérez",
        commercial_contact="",
    )

    by_tax_id = operator.get(URL, {"tax_id": "800.197"}).json()
    by_contact = operator.get(URL, {"commercial_contact": "laura"}).json()
    by_status = operator.get(URL, {"status": "INACTIVE"}).json()

    assert [c["name"] for c in by_tax_id["results"]] == ["Colegio Los Robles SAS"]
    assert by_contact["count"] == 1 and by_status["count"] == 0


def test_deactivated_customer_is_read_only_and_can_be_reactivated(operator):
    customer_id = create(operator).json()["id"]

    assert operator.post(f"{URL}{customer_id}/deactivate/").json()["is_active"] is False
    blocked = operator.post(f"{URL}{customer_id}/notes/", {"content": "Hola"}, format="json")
    assert blocked.status_code == 409
    assert operator.get(f"{URL}{customer_id}/").status_code == 200  # still visible
    assert operator.post(f"{URL}{customer_id}/activate/").json()["is_active"] is True


def test_history_is_empty_until_quotations_exist(operator):
    customer_id = create(operator).json()["id"]

    history = operator.get(f"{URL}{customer_id}/history/").json()

    assert history == {"count": 0, "page": 1, "page_size": 20, "total_pages": 0, "results": []}


def test_notes_lifecycle_and_author_rules(operator, logged_in_client):
    customer_id = create(operator).json()["id"]
    notes_url = f"{URL}{customer_id}/notes/"

    note = operator.post(notes_url, {"content": "Coordinar despacho con Laura"}, "json").json()
    assert note["author_name"] == "Ana Torres" and note["can_edit"] is True

    empty = operator.post(notes_url, {"content": "   "}, "json")
    assert empty.json()["errors"]["content"] == ["La nota no puede estar vacía."]

    edited = operator.patch(f"{notes_url}{note['id']}/", {"content": "Despacho el lunes"}, "json")
    assert edited.json()["is_edited"] is True

    admin = logged_in_client(RoleType.ADMIN)
    assert admin.get(notes_url).json()["results"][0]["can_edit"] is False
    not_author = admin.patch(f"{notes_url}{note['id']}/", {"content": "Cambio"}, "json")
    assert not_author.status_code == 403

    # Anyone with permission can delete it (US 2.24); the text stays in the audit log.
    assert admin.delete(f"{notes_url}{note['id']}/").status_code == 204
    assert operator.get(notes_url).json()["count"] == 0
    deleted = AuditEntryModel.objects.get(entity_id=note["id"], action="DELETED")
    assert deleted.old_values["content"] == "Despacho el lunes"


def test_requests_without_permission_or_session_are_denied():
    from rest_framework.test import APIClient

    assert APIClient().get(URL).status_code == 401
