"""End-to-end authentication flows through the REST API (real JWT, real TOTP codes)."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from modules.authentication.domain.session import SessionStatus
from modules.authentication.infrastructure.models import SessionModel, TotpEnrollmentModel
from modules.authentication.infrastructure.persistence.repositories import DjangoSessionRepository
from modules.shared_kernel.domain.security import RoleType
from modules.shared_kernel.infrastructure.models import AuditEntryModel

from ..conftest import DEFAULT_PASSWORD, enroll_and_login, totp_code

pytestmark = pytest.mark.django_db

EMAIL = "ana@empresa.com"


def login(client, email=EMAIL, password=DEFAULT_PASSWORD):
    return client.post("/api/auth/login/", {"email": email, "password": password}, "json")


def bearer(token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


# --- First login and enrollment (US 1.1, US 1.2) ----------------------------------------------


def test_first_login_requires_linking_the_authenticator(create_account):
    create_account()
    client = APIClient()

    challenge = login(client).json()
    assert challenge["step"] == "ENROLL_AUTHENTICATOR"

    enrollment = client.post(
        "/api/auth/enrollment/", {"pre_auth_token": challenge["pre_auth_token"]}, "json"
    ).json()
    assert enrollment["qr_code"].startswith("data:image/svg+xml;base64,")
    assert len(enrollment["secret"]) >= 16

    wrong = client.post(
        "/api/auth/enrollment/confirm/",
        {"pre_auth_token": challenge["pre_auth_token"], "code": "000000"},
        "json",
    )
    assert wrong.status_code == 401 and wrong.json()["code"] == "INVALID_CODE"

    stored = TotpEnrollmentModel.objects.get()
    assert enrollment["secret"] not in stored.encrypted_secret  # encrypted at rest


def test_three_wrong_enrollment_codes_lock_the_account(create_account):
    """FR-01-03/FR-01-14: a wrong pairing code counts as a failed attempt, like any other."""
    create_account()
    client = APIClient()
    challenge = login(client).json()
    token = challenge["pre_auth_token"]
    client.post("/api/auth/enrollment/", {"pre_auth_token": token}, "json")

    for _ in range(3):
        last = client.post(
            "/api/auth/enrollment/confirm/",
            {"pre_auth_token": token, "code": "000000"},
            "json",
        )

    assert last.json()["code"] == "ACCOUNT_LOCKED"
    assert AuditEntryModel.objects.filter(action="ACCOUNT_LOCKED").exists()


def test_confirmed_login_returns_access_token_and_httponly_refresh_cookie(create_account):
    create_account()
    client = APIClient()

    session = enroll_and_login(client, EMAIL)["session"]

    assert session["user"]["email"] == EMAIL and "USER_MANAGE" in session["user"]["permissions"]
    cookie = client.cookies["imsi_refresh"]
    assert cookie["httponly"] and cookie["samesite"] == "Strict" and cookie["path"] == "/api/auth/"
    me = client.get("/api/auth/me/", **bearer(session["access_token"]))
    assert me.status_code == 200 and me.json()["role"] == "ADMIN"


def test_expired_enrollment_shows_the_required_message(create_account):
    create_account()
    client = APIClient()
    token = login(client).json()["pre_auth_token"]
    secret = client.post("/api/auth/enrollment/", {"pre_auth_token": token}, "json").json()[
        "secret"
    ]
    TotpEnrollmentModel.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    response = client.post(
        "/api/auth/enrollment/confirm/",
        {"pre_auth_token": token, "code": totp_code(secret)},
        "json",
    )

    assert response.status_code == 409
    assert response.json()["detail"].startswith("El tiempo de vinculación ha expirado")


# --- Every other login (US 1.3) and single session (US 1.5) ------------------------------------


def test_second_login_asks_for_the_code_and_closes_the_previous_session(create_account):
    create_account()
    first = enroll_and_login(APIClient(), EMAIL)
    client = APIClient()

    challenge = login(client).json()
    assert challenge["step"] == "VERIFY_CODE"
    session = client.post(
        "/api/auth/verify/",
        {"pre_auth_token": challenge["pre_auth_token"], "code": totp_code(first["secret"], 1)},
        "json",
    )
    assert session.status_code == 200

    old = APIClient().get("/api/auth/me/", **bearer(first["session"]["access_token"]))
    assert old.status_code == 401 and old.json()["code"] == "SESSION_REPLACED"
    assert old.json()["detail"].startswith("Su sesión ha sido cerrada debido a un nuevo inicio")


def test_pre_auth_token_is_not_an_access_token(create_account):
    create_account()
    token = login(APIClient()).json()["pre_auth_token"]

    response = APIClient().get("/api/auth/me/", **bearer(token))

    assert response.status_code == 401


def test_malformed_code_is_rejected_without_counting_an_attempt(create_account):
    create_account()
    enroll_and_login(APIClient(), EMAIL)
    client = APIClient()
    token = login(client).json()["pre_auth_token"]

    response = client.post("/api/auth/verify/", {"pre_auth_token": token, "code": "12ab"}, "json")

    assert response.status_code == 400
    assert response.json()["errors"]["code"] == ["El código debe contener 6 dígitos."]
    assert not AuditEntryModel.objects.filter(action="LOGIN_FAILED").exists()


# --- Credentials errors and lockout (US 1.1, FR-01-14) -----------------------------------------


def test_unknown_email_and_wrong_password_get_the_same_message(create_account):
    create_account()
    client = APIClient()

    unknown = login(client, email="nadie@empresa.com").json()
    wrong = login(client, password="Otra#2026x").json()

    assert unknown["detail"] == wrong["detail"] == "Correo electrónico o contraseña incorrectos"


def test_three_wrong_passwords_lock_the_account_and_failures_are_persisted(create_account):
    create_account()
    client = APIClient()

    for _ in range(3):
        login(client, password="Mala#2026x")
    locked = login(client)  # even the right password is refused while locked

    assert locked.status_code == 401 and locked.json()["code"] == "ACCOUNT_LOCKED"
    assert "15 minutos" in locked.json()["detail"]
    actions = list(AuditEntryModel.objects.values_list("action", flat=True))
    assert actions.count("LOGIN_FAILED") == 3 and actions.count("ACCOUNT_LOCKED") == 1


def test_three_wrong_codes_lock_the_account(create_account):
    create_account()
    enroll_and_login(APIClient(), EMAIL)
    client = APIClient()

    for _ in range(3):
        token = login(client).json()["pre_auth_token"]
        last = client.post("/api/auth/verify/", {"pre_auth_token": token, "code": "000000"}, "json")

    assert last.json()["code"] == "ACCOUNT_LOCKED"
    assert login(client).json()["code"] == "ACCOUNT_LOCKED"


def test_inactive_account_with_correct_password(create_account, logged_in_client):
    target = create_account(email="marta@empresa.com", role=RoleType.OPERATOR)
    admin = logged_in_client(RoleType.ADMIN)
    admin.post(f"/api/users/{target.id}/deactivate/")

    response = login(APIClient(), email="marta@empresa.com").json()

    assert response["detail"] == "Su cuenta se encuentra desactivada. Contacte al administrador"


# --- Refresh, logout, inactivity, deactivation --------------------------------------------------


def test_refresh_rotates_the_cookie_and_detects_reuse(create_account):
    create_account()
    client = APIClient()
    enroll_and_login(client, EMAIL)
    old_cookie = client.cookies["imsi_refresh"].value

    refreshed = client.post("/api/auth/refresh/")
    assert refreshed.status_code == 200 and refreshed.json()["access_token"]
    assert client.cookies["imsi_refresh"].value != old_cookie

    attacker = APIClient()
    attacker.cookies["imsi_refresh"] = old_cookie
    assert attacker.post("/api/auth/refresh/").status_code == 401
    session = SessionModel.objects.get()
    assert session.status == "TERMINATED" and session.termination_reason == "TOKEN_REUSE"


def test_a_lost_refresh_race_does_not_kill_the_session(create_account):
    """Two tabs refresh with the same cookie: the loser fails, the winner stays open."""
    create_account()
    enroll_and_login(APIClient(), EMAIL)
    repository = DjangoSessionRepository()
    model = SessionModel.objects.get()
    first, second = repository.get(model.id), repository.get(model.id)
    previous = first.refresh_token_id

    first.rotate_refresh_token("winner")
    second.rotate_refresh_token("loser")

    assert repository.update(first, expected_refresh_token_id=previous) is True
    assert repository.update(second, expected_refresh_token_id=previous) is False
    stored = repository.get(model.id)
    assert stored.refresh_token_id == "winner" and stored.status is SessionStatus.ACTIVE


def test_logout_closes_the_session(create_account):
    create_account()
    client = APIClient()
    access = enroll_and_login(client, EMAIL)["session"]["access_token"]

    assert client.post("/api/auth/logout/", **bearer(access)).status_code == 204
    assert client.get("/api/auth/me/", **bearer(access)).json()["code"] == "SESSION_ENDED"


def test_session_expires_after_15_minutes_of_inactivity(create_account):
    create_account()
    client = APIClient()
    access = enroll_and_login(client, EMAIL)["session"]["access_token"]
    SessionModel.objects.update(last_activity_at=timezone.now() - timedelta(minutes=16))

    me = client.get("/api/auth/me/", **bearer(access))
    refresh = client.post("/api/auth/refresh/")

    assert me.json()["detail"] == "Su sesión ha caducado por inactividad"
    assert refresh.json()["code"] == "SESSION_EXPIRED"
    assert SessionModel.objects.get().termination_reason == "INACTIVITY"


def test_deactivating_an_account_closes_its_sessions(create_account, logged_in_client):
    target = create_account(email="marta@empresa.com", role=RoleType.OPERATOR)
    marta = APIClient()
    access = enroll_and_login(marta, "marta@empresa.com")["session"]["access_token"]
    admin = logged_in_client(RoleType.ADMIN)

    admin.post(f"/api/users/{target.id}/deactivate/")

    assert marta.get("/api/auth/me/", **bearer(access)).json()["code"] == "ACCOUNT_INACTIVE"
    assert SessionModel.objects.get(user_id=target.id).termination_reason == "ACCOUNT_DEACTIVATED"


# --- Real permissions on business endpoints ----------------------------------------------------


def test_requests_without_session_are_rejected():
    response = APIClient().get("/api/products/")

    assert response.status_code == 401


def test_permissions_come_from_the_real_session(logged_in_client):
    operator = logged_in_client(RoleType.OPERATOR)
    admin = logged_in_client(RoleType.ADMIN)
    payload = {"code": "SIL-001", "name": "Silla", "unit_of_measure": "Unidad"}

    assert operator.get("/api/products/").status_code == 200
    assert operator.post("/api/products/", payload, "json").status_code == 403
    created = admin.post("/api/products/", payload, "json")
    assert created.status_code == 201

    entry = AuditEntryModel.objects.get(entity_id=created.json()["id"])
    assert entry.actor_type == "USER" and entry.user_id is not None
