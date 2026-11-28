"""Fixtures shared by the export queue and export batch tests."""

import pytest

from modules.shared_kernel.domain.security import RoleType


@pytest.fixture
def admin(logged_in_client):
    return logged_in_client(RoleType.ADMIN)


@pytest.fixture
def operator(logged_in_client):
    return logged_in_client(RoleType.OPERATOR)


@pytest.fixture
def catalog(admin):
    def create(code, name):
        return admin.post(
            "/api/products/", {"code": code, "name": name, "unit_of_measure": "Unidad"}, "json"
        ).json()["id"]

    return {"chair": create("SIL-001", "Silla escolar"), "desk": create("MES-002", "Mesa")}


@pytest.fixture
def customer(admin):
    return admin.post(
        "/api/customers/",
        {
            "customer_type": "LEGAL_ENTITY",
            "tax_id": "800197268-4",
            "name": "Colegio Los Robles SAS",
            "address": "Calle 1 # 2-3",
            "primary_phone": "6011234567",
            "email": "compras@robles.edu.co",
        },
        "json",
    ).json()
