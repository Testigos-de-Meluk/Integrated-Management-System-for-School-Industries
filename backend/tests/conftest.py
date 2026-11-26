"""Shared fixtures: real accounts and real logins (JWT + TOTP), with synthetic data only."""

import time
from collections.abc import Callable

import pyotp
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from modules.shared_kernel.domain.security import RoleType
from modules.user_accounts.domain.user import User
from modules.user_accounts.infrastructure.dependencies import password_hasher
from modules.user_accounts.infrastructure.persistence.django_user_repository import (
    DjangoUserRepository,
)

DEFAULT_PASSWORD = "Segura#2026"


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Rate-limit counters and unknown-email lockouts live in the cache: no test inherits them."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def create_account(db) -> Callable[..., User]:
    def _create(
        email: str = "ana@empresa.com",
        role: RoleType = RoleType.ADMIN,
        password: str = DEFAULT_PASSWORD,
        full_name: str = "Ana Torres",
    ) -> User:
        user = User.register(full_name, email, "Cargo", role, password_hasher().hash(password))
        DjangoUserRepository().add(user)
        return user

    return _create


def totp_code(secret: str, steps_ahead: int = 0) -> str:
    """Code shown by the authenticator app now (or ``steps_ahead`` × 30 s later)."""
    return pyotp.TOTP(secret).at(time.time() + 30 * steps_ahead)


def enroll_and_login(client: APIClient, email: str, password: str = DEFAULT_PASSWORD) -> dict:
    """First login: password → QR → confirm. Returns the session body and the TOTP secret."""
    challenge = client.post("/api/auth/login/", {"email": email, "password": password}, "json")
    assert challenge.status_code == 200, challenge.json()
    token = challenge.json()["pre_auth_token"]
    secret = client.post("/api/auth/enrollment/", {"pre_auth_token": token}, "json").json()[
        "secret"
    ]
    confirmed = client.post(
        "/api/auth/enrollment/confirm/",
        {"pre_auth_token": token, "code": totp_code(secret)},
        "json",
    )
    assert confirmed.status_code == 200, confirmed.json()
    return {"session": confirmed.json(), "secret": secret}


@pytest.fixture
def logged_in_client(create_account) -> Callable[[RoleType], APIClient]:
    """An API client authenticated as a brand-new account with the given role."""

    def _client(role: RoleType = RoleType.ADMIN, email: str | None = None) -> APIClient:
        email = email or f"{role.value.lower()}@empresa.com"
        create_account(email=email, role=role)
        client = APIClient()
        session = enroll_and_login(client, email)["session"]
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {session['access_token']}")
        return client

    return _client
