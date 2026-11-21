from datetime import UTC, datetime, timedelta

import pytest

from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.security import RoleType
from modules.user_accounts.domain.exceptions import InvalidAccountStatusChange
from modules.user_accounts.domain.password_policy import PasswordPolicy
from modules.user_accounts.domain.user import LOCKOUT_DURATION, AccountStatus, User

NOW = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)


def make_user(**overrides) -> User:
    data = {
        "full_name": "Ana Torres",
        "email": "ana@industriasescolares.com",
        "job_title": "Dueña",
        "role": RoleType.ADMIN,
        "password_hash": "hash",
    } | overrides
    return User.register(**data)


def test_register_normalizes_email_and_starts_active():
    user = make_user(email="  Ana@IndustriasEscolares.COM ")

    assert user.email == "ana@industriasescolares.com"
    assert user.status is AccountStatus.ACTIVE
    assert user.last_access_at is None


@pytest.mark.parametrize("email", ["", "ana", "ana@", "ana@empresa", "a b@c.com"])
def test_register_rejects_invalid_emails(email):
    with pytest.raises(ValidationError) as error:
        make_user(email=email)

    assert "email" in error.value.errors


def test_snapshot_never_contains_the_password_hash():
    assert "password_hash" not in make_user().snapshot()


def test_deactivate_and_activate():
    user = make_user()
    user.deactivate()
    assert not user.is_active
    with pytest.raises(InvalidAccountStatusChange):
        user.deactivate()
    user.activate()
    assert user.is_active


def test_three_consecutive_failures_lock_the_account_for_15_minutes():
    user = make_user()

    assert user.register_failed_login(NOW) is False
    assert user.register_failed_login(NOW) is False
    assert user.register_failed_login(NOW) is True

    assert user.is_locked(NOW + timedelta(minutes=14))
    assert not user.is_locked(NOW + LOCKOUT_DURATION)


def test_successful_login_resets_the_counter():
    user = make_user()
    user.register_failed_login(NOW)
    user.register_failed_login(NOW)

    user.register_successful_login(NOW)
    assert user.register_failed_login(NOW) is False  # counting starts again
    assert user.last_access_at == NOW


def test_manual_unlock():
    user = make_user()
    for _ in range(3):
        user.register_failed_login(NOW)

    user.unlock()

    assert not user.is_locked(NOW)


@pytest.mark.parametrize(
    "password, valid",
    [
        ("Segura#2026", True),
        ("corta#1A", True),
        ("sinmayus#1", False),
        ("SINMINUS#1", False),
        ("SinNumero#", False),
        ("SinEspecial1", False),
        ("Ab#1", False),
    ],
)
def test_password_policy(password, valid):
    assert PasswordPolicy().is_satisfied_by(password) is valid


def test_generated_passwords_always_satisfy_the_policy():
    policy = PasswordPolicy()
    assert all(policy.is_satisfied_by(policy.generate()) for _ in range(200))
