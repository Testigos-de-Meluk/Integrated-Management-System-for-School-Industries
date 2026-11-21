"""Bootstrap and recovery commands."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from rest_framework.test import APIClient

from modules.authentication.infrastructure.models import SessionModel, TotpEnrollmentModel
from modules.shared_kernel.infrastructure.models import AuditEntryModel

from ..conftest import enroll_and_login

pytestmark = pytest.mark.django_db


def run(*args) -> str:
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def printed_password(output: str) -> str:
    line = next(line for line in output.splitlines() if "se muestra una sola vez" in line)
    return line.rsplit(": ", 1)[1].strip()


def test_create_superadmin_prints_a_working_password():
    output = run("create_superadmin", "--email", "jefe@empresa.com", "--name", "Carlos Ríos")
    password = printed_password(output)

    response = APIClient().post(
        "/api/auth/login/", {"email": "jefe@empresa.com", "password": password}, "json"
    )
    assert response.status_code == 200


def test_reset_password_replaces_it_closes_sessions_and_can_unlink_the_authenticator(
    create_account,
):
    create_account(email="ana@empresa.com")
    enroll_and_login(APIClient(), "ana@empresa.com")

    output = run("reset_password", "--email", "ana@empresa.com", "--reset-authenticator")
    password = printed_password(output)

    login = APIClient().post(
        "/api/auth/login/", {"email": "ana@empresa.com", "password": password}, "json"
    )
    assert login.json()["step"] == "ENROLL_AUTHENTICATOR"
    assert not TotpEnrollmentModel.objects.exists()
    assert SessionModel.objects.get().termination_reason == "PASSWORD_CHANGED"
    assert AuditEntryModel.objects.filter(actor_label="reset_password").exists()


def test_reset_password_for_unknown_email_fails():
    with pytest.raises(CommandError):
        run("reset_password", "--email", "nadie@empresa.com")
