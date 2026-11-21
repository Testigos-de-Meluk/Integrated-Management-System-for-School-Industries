"""REST API integration tests (database required)."""

import pytest
from rest_framework.test import APIClient

from modules.products.domain.exceptions import DUPLICATE_CODE_MESSAGE

pytestmark = pytest.mark.django_db

URL = "/api/products/"


@pytest.fixture
def client():
    return APIClient()


def as_role(client, role):
    client.credentials(HTTP_X_DEV_ROLE=role)
    return client


def create(client, code="SIL-001", name="Silla escolar", unit="Unidad"):
    return client.post(URL, {"code": code, "name": name, "unit_of_measure": unit}, format="json")


def test_full_lifecycle_as_admin(client):
    as_role(client, "ADMIN")

    created = create(client)
    assert created.status_code == 201
    product_id = created.json()["id"]

    updated = client.patch(
        f"{URL}{product_id}/", {"name": "Silla infantil", "unit_of_measure": "Unidad"}, "json"
    )
    assert updated.json()["name"] == "Silla infantil"

    deactivated = client.post(f"{URL}{product_id}/deactivate/")
    assert deactivated.json()["status"] == "INACTIVE"
    assert deactivated.json()["is_selectable"] is False

    again = client.post(f"{URL}{product_id}/deactivate/")
    assert again.status_code == 409


def test_duplicate_code_returns_field_error(client):
    as_role(client, "ADMIN")
    create(client)

    response = create(client, code="sil-001")

    assert response.status_code == 400
    assert response.json()["errors"] == {"code": [DUPLICATE_CODE_MESSAGE]}


def test_missing_fields_return_field_errors(client):
    as_role(client, "ADMIN")

    response = client.post(URL, {}, format="json")

    assert response.status_code == 400
    assert set(response.json()["errors"]) == {"code", "name", "unit_of_measure"}


def test_operator_has_read_only_access(client):
    as_role(client, "ADMIN")
    create(client)
    as_role(client, "OPERATOR")

    assert client.get(URL).status_code == 200
    denied = create(client, code="MES-002")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "No tiene permisos para realizar esta acción."


def test_list_is_paginated_and_filtered(client):
    as_role(client, "ADMIN")
    for i in range(1, 26):
        create(client, code=f"SIL-{i:03d}", name=f"Silla {i}")
    create(client, code="MES-001", name="Mesa")

    first_page = client.get(URL, {"name": "silla", "page_size": 10}).json()
    assert first_page["count"] == 25
    assert first_page["total_pages"] == 3
    assert len(first_page["results"]) == 10
    assert first_page["results"][0]["code"] == "SIL-001"

    too_big = client.get(URL, {"page_size": 51})
    assert too_big.status_code == 400


def test_unknown_product_returns_404(client):
    as_role(client, "ADMIN")
    response = client.get(f"{URL}00000000-0000-0000-0000-000000000000/")

    assert response.status_code == 404
