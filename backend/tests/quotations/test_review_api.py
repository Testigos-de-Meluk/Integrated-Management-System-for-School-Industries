"""The quotation review API, end to end: request in the public assistant → review → approval."""

from datetime import timedelta

import pytest
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from modules.quotations.infrastructure.models import QuotationModel
from modules.shared_kernel.domain.security import RoleType
from modules.shared_kernel.infrastructure.models import AuditEntryModel

pytestmark = pytest.mark.django_db

BASE = "/api/quotations/"
LATER = (timezone.localdate() + timedelta(days=20)).isoformat()


@pytest.fixture(autouse=True)
def clear_rate_limits():
    cache.clear()


@pytest.fixture
def admin(logged_in_client):
    return logged_in_client(RoleType.ADMIN)


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


def request_quotation(catalog, **overrides):
    body = {
        "full_name": "Laura Méndez",
        "email": "laura@colegio.edu.co",
        "phone": "310 456 7890",
        "institution": "Colegio Los Robles",
        "tax_id": "800.197.268-4",
        "data_consent": True,
        "items": [
            {"product_id": catalog["chair"], "quantity": 40},
            {"product_id": catalog["desk"], "quantity": 10},
        ],
    } | overrides
    response = APIClient().post("/api/chatbot/quotations/", body, "json")
    assert response.status_code == 201
    return response.json()["id"]


def test_operator_is_denied(logged_in_client, catalog):
    quotation_id = request_quotation(catalog)
    operator = logged_in_client(RoleType.OPERATOR)

    assert operator.get(BASE).status_code == 403
    response = operator.post(f"{BASE}{quotation_id}/reject/", {"reason": "No"}, "json")
    assert response.status_code == 403
    assert response.json()["detail"] == "No tiene permisos para realizar esta acción."


def test_list_and_filters(admin, catalog):
    first = request_quotation(catalog)
    request_quotation(
        catalog,
        full_name="Pedro Ruiz",
        email="pedro@otro.edu.co",
        items=[{"product_id": catalog["desk"], "quantity": 3}],
    )
    admin.post(f"{BASE}{first}/reject/", {"reason": "Duplicada"}, "json")

    page = admin.get(BASE).json()
    assert page["count"] == 2
    assert page["results"][0]["requester_name"] == "Pedro Ruiz"  # newest first
    assert page["results"][1]["products"] == ["Silla escolar", "Mesa"]

    def numbers(**query):
        return [r["requester_name"] for r in admin.get(BASE, query).json()["results"]]

    assert numbers(contact="pedro") == ["Pedro Ruiz"]
    assert numbers(product="SIL-001") == ["Laura Méndez"]
    assert numbers(status="REJECTED") == ["Laura Méndez"]
    assert numbers(issued_from=LATER) == []
    assert numbers(contact="laura", status="PENDING_REVIEW") == []  # filters combine (AND)
    bad = admin.get(BASE, {"status": "X"})
    assert bad.status_code == 400 and "status" in bad.json()["errors"]


def test_review_flow_end_to_end(admin, catalog, customer, django_capture_on_commit_callbacks):
    quotation_id = request_quotation(catalog)

    detail = admin.get(f"{BASE}{quotation_id}/").json()
    assert detail["status"] == "PENDING_REVIEW"
    assert detail["suggested_customer"]["id"] == customer["id"]
    chair, desk = detail["items"]

    incomplete = admin.post(
        f"{BASE}{quotation_id}/approve/",
        {"prices": [{"item_id": chair["id"], "final_unit_price": "180000"}], "dispatch_date": None},
        "json",
    )
    assert incomplete.status_code == 400
    assert set(incomplete.json()["errors"]) == {"items", "dispatch_date"}

    modified = admin.post(
        f"{BASE}{quotation_id}/modify/",
        {
            "items": [
                {"product_id": catalog["chair"], "quantity": 35, "final_unit_price": "180000"},
                {"product_id": catalog["desk"], "quantity": 10},
            ],
            "reason": "Ajuste de cantidades acordado por teléfono",
            "dispatch_date": LATER,
        },
        "json",
    )
    assert modified.status_code == 200 and modified.json()["status"] == "MODIFIED"

    linked = admin.post(f"{BASE}{quotation_id}/customer/", {"customer_id": customer["id"]}, "json")
    assert linked.json()["customer"]["name"] == "Colegio Los Robles SAS"

    with django_capture_on_commit_callbacks(execute=True):
        approved = admin.post(
            f"{BASE}{quotation_id}/approve/",
            {
                "prices": [{"item_id": desk["id"], "final_unit_price": "420000"}],
                "dispatch_date": LATER,
                "commercial_terms": "Pago a 30 días",
            },
            "json",
        )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "APPROVED" and body["final_total"] == str(35 * 180000 + 10 * 420000)
    stored = QuotationModel.objects.get(pk=quotation_id)
    assert stored.final_total == 35 * 180000 + 10 * 420000 and stored.approved_by_id is not None
    assert mail.outbox[-1].to == ["laura@colegio.edu.co"]
    assert "aprobada" in mail.outbox[-1].subject
    actions = set(
        AuditEntryModel.objects.filter(entity_id=quotation_id).values_list("action", flat=True)
    )
    assert {"CREATED", "UPDATED", "APPROVED"} <= actions

    locked = admin.post(f"{BASE}{quotation_id}/reject/", {"reason": "Tarde"}, "json")
    assert locked.status_code == 409 and locked.json()["code"] == "QUOTATION_LOCKED"

    pdf = admin.get(f"{BASE}{quotation_id}/pdf/")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # The customer 360 profile now lists it (US 2.20).
    history = admin.get(f"/api/customers/{customer['id']}/history/").json()
    assert [(h["document_type"], h["status"]) for h in history["results"]] == [
        ("QUOTATION", "APPROVED")
    ]

    # The approved final price feeds the next estimate (US 2.28.3).
    estimate = APIClient().post(
        "/api/chatbot/estimate/",
        {"items": [{"product_id": catalog["chair"], "quantity": 1}]},
        "json",
    )
    assert estimate.json()["items"][0]["unit_price_min"] == "180000"


def test_reject_requires_a_reason(admin, catalog, django_capture_on_commit_callbacks):
    quotation_id = request_quotation(catalog)

    missing = admin.post(f"{BASE}{quotation_id}/reject/", {"reason": ""}, "json")
    assert missing.status_code == 400 and "reason" in missing.json()["errors"]

    with django_capture_on_commit_callbacks(execute=True):
        rejected = admin.post(f"{BASE}{quotation_id}/reject/", {"reason": "Sin stock"}, "json")
    assert rejected.json()["status"] == "REJECTED"
    assert "Sin stock" in mail.outbox[-1].body
