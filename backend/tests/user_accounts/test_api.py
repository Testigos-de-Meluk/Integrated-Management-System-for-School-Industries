"""REST API integration tests for user accounts and the database audit log."""

import pytest
from django.core import mail
from rest_framework.test import APIClient

from modules.shared_kernel.infrastructure.models import AuditEntryModel
from modules.user_accounts.domain.exceptions import DUPLICATE_EMAIL_MESSAGE
from modules.user_accounts.infrastructure.models import UserModel

pytestmark = pytest.mark.django_db

URL = "/api/users/"


@pytest.fixture
def client():
    client = APIClient()
    client.credentials(HTTP_X_DEV_ROLE="ADMIN")
    return client


def create(client, email="marta@empresa.com", **overrides):
    payload = {
        "full_name": "Marta Ruiz",
        "email": email,
        "job_title": "Secretaria",
        "role": "OPERATOR",
        "password": "Segura#2026",
    } | overrides
    return client.post(URL, payload, format="json")


def test_create_user_stores_bcrypt_hash_audits_and_emails(
    client, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        response = create(client)

    assert response.status_code == 201
    body = response.json()
    assert "password" not in body and "password_hash" not in body
    stored = UserModel.objects.get(email="marta@empresa.com")
    assert stored.password_hash.startswith("$2b$")  # bcrypt
    assert AuditEntryModel.objects.filter(entity_id=body["id"], action="CREATED").exists()
    assert len(mail.outbox) == 1 and "Segura#2026" in mail.outbox[0].body


def test_duplicate_email_and_weak_password_errors(client):
    create(client)

    duplicate = create(client, email="MARTA@empresa.com")
    assert duplicate.status_code == 400
    assert duplicate.json()["errors"] == {"email": [DUPLICATE_EMAIL_MESSAGE]}

    weak = create(client, email="otra@empresa.com", password="debil")
    assert weak.status_code == 400 and "password" in weak.json()["errors"]


def test_email_cannot_be_changed(client):
    user_id = create(client).json()["id"]

    response = client.patch(
        f"{URL}{user_id}/",
        {"full_name": "Marta R.", "job_title": "Contadora", "role": "ADMIN", "email": "x@y.com"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["email"] == "marta@empresa.com"


def test_lifecycle_deactivate_activate_unlock_and_password(client):
    user_id = create(client).json()["id"]

    assert client.post(f"{URL}{user_id}/deactivate/").json()["status"] == "INACTIVE"
    assert client.post(f"{URL}{user_id}/deactivate/").status_code == 409
    assert client.post(f"{URL}{user_id}/activate/").json()["status"] == "ACTIVE"
    assert client.post(f"{URL}{user_id}/unlock/").json()["is_locked"] is False
    generated = client.post(f"{URL}{user_id}/password/", {"generate_password": True}, format="json")
    assert generated.status_code == 200


def test_operator_is_denied(client):
    client.credentials(HTTP_X_DEV_ROLE="OPERATOR")

    assert client.get(URL).status_code == 403


def test_list_filters_by_role_and_name(client):
    create(client, email="a@empresa.com", full_name="Ana Torres", role="ADMIN")
    create(client, email="b@empresa.com", full_name="Marta Ruiz", role="OPERATOR")

    page = client.get(URL, {"role": "OPERATOR", "name": "marta"}).json()

    assert page["count"] == 1 and page["results"][0]["email"] == "b@empresa.com"


def test_products_changes_are_written_to_the_audit_table(client):
    response = client.post(
        "/api/products/", {"code": "SIL-001", "name": "Silla", "unit_of_measure": "Unidad"}, "json"
    )

    entry = AuditEntryModel.objects.get(entity_id=response.json()["id"])
    assert entry.action == "CREATED" and entry.entity_type == "Product"
    assert entry.new_values["code"] == "SIL-001"
    assert entry.source_ip == "127.0.0.1"
