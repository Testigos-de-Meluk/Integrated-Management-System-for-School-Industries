"""The public virtual assistant API, end to end (no account needed)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from modules.quotations.infrastructure.models import QuotationItemModel, QuotationModel
from modules.shared_kernel.domain.security import RoleType
from modules.shared_kernel.infrastructure.models import AuditEntryModel

pytestmark = pytest.mark.django_db

BASE = "/api/chatbot/"


@pytest.fixture(autouse=True)
def clear_rate_limits():
    cache.clear()


@pytest.fixture
def products(logged_in_client):
    """Two active products and one inactive, created by an Administrador."""
    admin = logged_in_client(RoleType.ADMIN)

    def create(code, name):
        return admin.post(
            "/api/products/", {"code": code, "name": name, "unit_of_measure": "Unidad"}, "json"
        ).json()["id"]

    chair, desk, old = (
        create("SIL-001", "Silla escolar"),
        create("MES-002", "Mesa"),
        create("SIL-006", "Silla antigua"),
    )
    admin.post(f"/api/products/{old}/deactivate/")
    return {"chair": chair, "desk": desk, "old": old}


def request_body(products, **overrides):
    return {
        "full_name": "Laura Méndez",
        "email": "laura@colegio.edu.co",
        "phone": "310 456 7890",
        "institution": "Colegio Los Robles SAS",
        "tax_id": "800197268-4",
        "data_consent": True,
        "items": [
            {"product_id": products["chair"], "quantity": 40},
            {"product_id": products["desk"], "quantity": 10},
        ],
    } | overrides


def approve_history(product_id, prices):
    """Simulates approved quotations (sub-step 4b) to feed the statistical estimator."""
    for index, price in enumerate(prices):
        quotation = QuotationModel.objects.create(
            quotation_number=f"COT-2025-{index + 1:04d}",
            issued_at=timezone.now() - timedelta(days=30),
            requester_full_name="X",
            requester_email="x@x.co",
            requester_phone="3000000000",
            valid_until=timezone.now().date(),
            status="APPROVED",
            access_key="k",
        )
        QuotationItemModel.objects.create(
            quotation=quotation,
            product_id=product_id,
            product_code="SIL-001",
            description="Silla",
            unit_of_measure="Unidad",
            quantity=10,
            final_unit_price=Decimal(price),
        )


def test_public_catalog_lists_only_active_products_without_prices(products):
    page = APIClient().get(f"{BASE}catalog/", {"search": "silla"}).json()

    assert [p["code"] for p in page["results"]] == ["SIL-001"]
    assert set(page["results"][0]) == {"id", "code", "name", "unit_of_measure"}


def test_estimate_with_and_without_history(products):
    approve_history(products["chair"], [170000, 180000, 190000])

    estimate = (
        APIClient()
        .post(f"{BASE}estimate/", {"items": request_body(products)["items"]}, "json")
        .json()
    )

    chair, desk = estimate["items"]
    assert (chair["unit_price_min"], chair["unit_price_max"]) == ("175000", "185000")
    assert desk["unit_price_min"] is None and estimate["unpriced_items"] == 1


def test_request_quotation_end_to_end(products, django_capture_on_commit_callbacks):
    client = APIClient()

    response = client.post(f"{BASE}quotations/", request_body(products), "json")
    assert response.status_code == 201
    quotation = response.json()
    assert quotation["number"] == f"COT-{timezone.now().year}-0001"
    stored = QuotationModel.objects.get(pk=quotation["id"])
    assert stored.status == "PENDING_REVIEW" and stored.requester_tax_id == "800197268-4"
    assert AuditEntryModel.objects.filter(
        entity_id=quotation["id"], actor_type="ANONYMOUS"
    ).exists()

    key = quotation["access_key"]
    pdf = client.get(f"{BASE}quotations/{quotation['id']}/pdf/", {"key": key})
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    assert client.get(f"{BASE}quotations/{quotation['id']}/pdf/", {"key": "x"}).status_code == 404

    with django_capture_on_commit_callbacks(execute=True):
        sent = client.post(f"{BASE}quotations/{quotation['id']}/email/", {"key": key}, "json")
    assert sent.status_code == 202 and sent.json() == {"sent_to": "laura@colegio.edu.co"}
    assert mail.outbox[0].attachments[0][0] == f"{quotation['number']}.pdf"

    second = client.post(f"{BASE}quotations/", request_body(products), "json").json()
    assert second["number"].endswith("-0002")


def test_validation_errors(products):
    client = APIClient()

    no_consent = client.post(
        f"{BASE}quotations/", request_body(products, data_consent=False), "json"
    )
    assert "data_consent" in no_consent.json()["errors"]

    inactive = client.post(
        f"{BASE}quotations/",
        request_body(products, items=[{"product_id": products["old"], "quantity": 2}]),
        "json",
    )
    assert inactive.status_code == 400 and "items" in inactive.json()["errors"]

    zero = client.post(
        f"{BASE}estimate/", {"items": [{"product_id": products["chair"], "quantity": 0}]}, "json"
    )
    assert zero.status_code == 400


def test_quotation_requests_are_rate_limited(products, monkeypatch):
    # DRF reads the rates once, when the class is imported: patch them directly.
    monkeypatch.setattr(
        ScopedRateThrottle,
        "THROTTLE_RATES",
        {**ScopedRateThrottle.THROTTLE_RATES, "public_quotation": "2/hour"},
    )
    client = APIClient()
    for _ in range(2):
        client.post(f"{BASE}quotations/", request_body(products), "json")

    assert client.post(f"{BASE}quotations/", request_body(products), "json").status_code == 429
