"""Work orders through the REST API with real sessions (US 2.35 … US 2.40, step 5 version)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from modules.quotations.infrastructure.models import QuotationModel
from modules.shared_kernel.domain.document_numbers import business_date
from modules.shared_kernel.domain.security import RoleType
from modules.shared_kernel.infrastructure.models import AuditEntryModel
from modules.work_orders.infrastructure.models import WorkOrderModel

pytestmark = pytest.mark.django_db

BASE = "/api/work-orders/"
TODAY = business_date(timezone.now())
LATER = (TODAY + timedelta(days=20)).isoformat()


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


def approved_quotation(admin, catalog, name="Laura Méndez"):
    """Requested in the public portal and approved by the Administrador (step 4)."""
    body = {
        "full_name": name,
        "email": "laura@colegio.edu.co",
        "phone": "310 456 7890",
        "institution": "Colegio Los Robles",
        "data_consent": True,
        "items": [
            {"product_id": catalog["chair"], "quantity": 40},
            {"product_id": catalog["desk"], "quantity": 10},
        ],
    }
    quotation_id = APIClient().post("/api/chatbot/quotations/", body, "json").json()["id"]
    items = admin.get(f"/api/quotations/{quotation_id}/").json()["items"]
    response = admin.post(
        f"/api/quotations/{quotation_id}/approve/",
        {
            "prices": [{"item_id": i["id"], "final_unit_price": "150000"} for i in items],
            "dispatch_date": LATER,
        },
        "json",
    )
    assert response.status_code == 200
    return quotation_id


def test_the_operator_generates_an_order_and_the_quotation_gets_its_customer(
    admin, operator, catalog, customer
):
    quotation_id = approved_quotation(admin, catalog)

    available = operator.get(f"{BASE}available-quotations/").json()
    assert [q["id"] for q in available["results"]] == [quotation_id]
    assert available["results"][0]["customer_id"] is None

    missing = operator.post(BASE, {"quotation_id": quotation_id}, "json")
    assert missing.status_code == 400 and "customer_id" in missing.json()["errors"]

    created = operator.post(
        BASE, {"quotation_id": quotation_id, "customer_id": customer["id"]}, "json"
    )
    assert created.status_code == 201
    order = created.json()
    assert order["number"] == f"OT-{TODAY:%Y%m%d}-00001" and order["status"] == "PENDING"
    assert order["agreed_delivery_date"] == LATER and order["can_edit"]
    assert QuotationModel.objects.get(pk=quotation_id).customer_id is not None
    assert AuditEntryModel.objects.filter(entity_type="WorkOrder", action="CREATED").exists()

    assert operator.get(f"{BASE}available-quotations/").json()["count"] == 0
    duplicate = operator.post(BASE, {"quotation_id": quotation_id}, "json")
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ACTIVE_WORK_ORDER_EXISTS"


def test_the_operator_still_cannot_review_quotations(operator):
    assert operator.get("/api/quotations/").status_code == 403


def test_list_filters_edit_cancel_and_generate_again(admin, operator, catalog, customer):
    first_quotation = approved_quotation(admin, catalog)
    second_quotation = approved_quotation(admin, catalog, name="Pedro Ruiz")
    first = operator.post(
        BASE, {"quotation_id": first_quotation, "customer_id": customer["id"]}, "json"
    ).json()
    operator.post(BASE, {"quotation_id": second_quotation, "customer_id": customer["id"]}, "json")

    page = operator.get(BASE, {"number": first["number"]}).json()
    assert page["count"] == 1 and page["results"][0]["id"] == first["id"]
    assert operator.get(BASE, {"product": "mesa"}).json()["count"] == 2
    assert operator.get(BASE, {"customer": "robles"}).json()["count"] == 2
    assert operator.get(BASE, {"status": "CANCELLED"}).json()["count"] == 0

    edited = operator.patch(
        f"{BASE}{first['id']}/",
        {
            "customer_id": customer["id"],
            "items": [{"product_id": catalog["chair"], "quantity": 12}],
            "agreed_delivery_date": LATER,
        },
        "json",
    )
    assert edited.status_code == 200 and len(edited.json()["items"]) == 1

    no_reason = operator.post(f"{BASE}{first['id']}/cancel/", {"reason": ""}, "json")
    assert no_reason.status_code == 400
    annulled = operator.post(f"{BASE}{first['id']}/cancel/", {"reason": "Pedido duplicado"}, "json")
    assert annulled.json()["status"] == "CANCELLED"
    locked = operator.patch(
        f"{BASE}{first['id']}/",
        {
            "customer_id": customer["id"],
            "items": [{"product_id": catalog["chair"], "quantity": 1}],
            "agreed_delivery_date": LATER,
        },
        "json",
    )
    assert locked.status_code == 409 and locked.json()["code"] == "WORK_ORDER_NOT_EDITABLE"

    again = operator.post(BASE, {"quotation_id": first_quotation}, "json")
    assert again.status_code == 201 and again.json()["number"].endswith("-00003")


def test_reconcile_after_the_export_with_the_real_dispatch_date(admin, operator, catalog, customer):
    quotation_id = approved_quotation(admin, catalog)
    order = operator.post(
        BASE, {"quotation_id": quotation_id, "customer_id": customer["id"]}, "json"
    ).json()

    too_early = operator.post(
        f"{BASE}{order['id']}/reconcile/", {"actual_dispatch_date": TODAY.isoformat()}, "json"
    )
    assert too_early.status_code == 409  # still Pendiente: no jumps

    # As the export does (step 5d):
    WorkOrderModel.objects.filter(pk=order["id"]).update(status="REGISTERED_IN_ACCOUNTING")
    future = (TODAY + timedelta(days=1)).isoformat()
    assert (
        operator.post(
            f"{BASE}{order['id']}/reconcile/", {"actual_dispatch_date": future}, "json"
        ).status_code
        == 400
    )
    done = operator.post(
        f"{BASE}{order['id']}/reconcile/", {"actual_dispatch_date": TODAY.isoformat()}, "json"
    ).json()

    assert done["status"] == "RECONCILED" and done["was_exported"] and done["can_cancel"]
    assert not done["can_edit"] and not done["can_reconcile"]


def test_unknown_orders_and_unapproved_quotations_are_not_found(operator, catalog):
    assert operator.get(f"{BASE}00000000-0000-0000-0000-000000000000/").status_code == 404
    pending = (
        APIClient()
        .post(
            "/api/chatbot/quotations/",
            {
                "full_name": "Laura Méndez",
                "email": "laura@colegio.edu.co",
                "phone": "310 456 7890",
                "data_consent": True,
                "items": [{"product_id": catalog["chair"], "quantity": 1}],
            },
            "json",
        )
        .json()["id"]
    )
    assert operator.post(BASE, {"quotation_id": pending}, "json").status_code == 404
