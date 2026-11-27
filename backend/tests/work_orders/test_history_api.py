"""Step 5b end to end: real dispatches feed the suggested date; O.T.s in the 360 profile."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from modules.shared_kernel.domain.business_days import add_business_days, is_business_day
from modules.shared_kernel.domain.document_numbers import business_date
from modules.shared_kernel.domain.security import RoleType
from modules.work_orders.infrastructure.models import WorkOrderModel

from .test_api import approved_quotation

pytestmark = pytest.mark.django_db

TODAY = business_date(timezone.now())


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


def dispatched_order(admin, operator, catalog, customer, business_days):
    """An approved quotation whose O.T. was dispatched that many business days after approval."""
    quotation_id = approved_quotation(admin, catalog)
    order = operator.post(
        "/api/work-orders/", {"quotation_id": quotation_id, "customer_id": customer["id"]}, "json"
    ).json()
    approved = TODAY - timedelta(days=60)
    WorkOrderModel.objects.filter(pk=order["id"]).update(
        status="RECONCILED",
        quotation_approved_at=timezone.now() - timedelta(days=60),
        actual_dispatch_date=add_business_days(approved, business_days),
    )
    return order


def test_reconciled_orders_feed_the_suggested_dispatch_date(admin, operator, catalog, customer):
    body = {
        "full_name": "Pedro Ruiz",
        "email": "pedro@colegio.edu.co",
        "phone": "310 456 7890",
        "data_consent": True,
        "items": [
            {"product_id": catalog["chair"], "quantity": 40},
            {"product_id": catalog["desk"], "quantity": 10},
        ],
    }
    before = APIClient().post("/api/chatbot/quotations/", body, "json").json()
    assert before["estimated_dispatch_date"] is None  # no history yet

    for days in (8, 10, 12):  # each order has 40 chairs and 10 desks
        dispatched_order(admin, operator, catalog, customer, days)

    after = APIClient().post("/api/chatbot/quotations/", body, "json").json()
    expected = add_business_days(TODAY, 10)
    assert after["estimated_dispatch_date"] == expected.isoformat()
    assert is_business_day(expected)

    # The review recalculates it: the first request (no history then) now gets a suggestion.
    review = admin.get(f"/api/quotations/{before['id']}/").json()
    assert review["estimated_dispatch_date"] is None
    assert review["suggested_dispatch_date"] == expected.isoformat()


def test_annulled_orders_do_not_count(admin, operator, catalog, customer):
    orders = [dispatched_order(admin, operator, catalog, customer, d) for d in (8, 10, 12)]
    WorkOrderModel.objects.filter(pk=orders[0]["id"]).update(status="CANCELLED")
    body = {
        "full_name": "Pedro Ruiz",
        "email": "pedro@colegio.edu.co",
        "phone": "310 456 7890",
        "data_consent": True,
        "items": [{"product_id": catalog["chair"], "quantity": 40}],
    }
    quotation = APIClient().post("/api/chatbot/quotations/", body, "json").json()
    assert quotation["estimated_dispatch_date"] is None  # only 2 valid samples left


def test_the_360_profile_lists_quotations_and_work_orders_apart(admin, operator, catalog, customer):
    order = dispatched_order(admin, operator, catalog, customer, 5)
    url = f"/api/customers/{customer['id']}/history/"

    quotations = operator.get(url).json()
    work_orders = operator.get(url, {"type": "WORK_ORDER"}).json()

    assert quotations["count"] == 1 and quotations["results"][0]["document_type"] == "QUOTATION"
    assert work_orders["count"] == 1
    entry = work_orders["results"][0]
    assert entry["id"] == order["id"] and entry["reference"] == order["number"]
    assert entry["status"] == "RECONCILED"
    assert operator.get(url, {"type": "OTHER"}).status_code == 400


def test_holidays_for_the_screens(operator):
    response = operator.get("/api/calendar/holidays/", {"year": 2026}).json()
    assert "2026-12-25" in response["holidays"] and len(response["holidays"]) == 18
    assert APIClient().get("/api/calendar/holidays/", {"year": 2026}).status_code == 401
