"""User account use cases with in-memory adapters (no database, no SMTP)."""

from uuid import uuid4

import pytest

from modules.shared_kernel.domain.audit import AuditAction
from modules.shared_kernel.domain.exceptions import PermissionDeniedError, ValidationError
from modules.shared_kernel.domain.pagination import PageRequest
from modules.shared_kernel.domain.security import Actor, RoleType
from modules.user_accounts.application.user_account_service import UserAccountService
from modules.user_accounts.domain.events import UserDeactivated, UserPasswordChanged
from modules.user_accounts.domain.exceptions import (
    DUPLICATE_EMAIL_MESSAGE,
    DuplicateEmail,
    SelfManagementNotAllowed,
)
from modules.user_accounts.ports.inbound.user_account_use_cases import (
    ChangePasswordCommand,
    CreateUserCommand,
    UpdateUserCommand,
    UserFilters,
)

from ..shared_fakes import FakePasswordHasher, SpyAuditLogger, SpyEventPublisher, SpyNotifier
from .fakes import InMemoryUserRepository

ADMIN = Actor.for_role(RoleType.ADMIN, user_id=uuid4())
OPERATOR = Actor.for_role(RoleType.OPERATOR, user_id=uuid4())


@pytest.fixture
def deps():
    return {
        "repository": InMemoryUserRepository(),
        "password_hasher": FakePasswordHasher(),
        "notifier": SpyNotifier(),
        "audit_logger": SpyAuditLogger(),
        "events": SpyEventPublisher(),
    }


@pytest.fixture
def service(deps):
    return UserAccountService(**deps, login_url="http://imsi.test/login")


def create(service, email="marta@empresa.com", role="OPERATOR", actor=ADMIN, **kwargs):
    command = CreateUserCommand(
        full_name="Marta Ruiz",
        email=email,
        job_title="Secretaria",
        role=role,
        **({"password": "Segura#2026"} | kwargs),
    )
    return service.create_user(actor, command)


def test_create_user_hashes_password_audits_and_emails_credentials(service, deps):
    view = create(service)

    stored = deps["repository"].get_by_id(view.id)
    assert stored.password_hash == "hashed:Segura#2026"
    assert view.status == "ACTIVE" and view.last_access_at is None
    assert [r.action for r in deps["audit_logger"].records] == [AuditAction.CREATED]
    email = deps["notifier"].sent[0]
    assert email.to == ("marta@empresa.com",)
    assert "Segura#2026" in email.body and "http://imsi.test/login" in email.body


def test_generated_password_is_emailed(service, deps):
    create(service, password=None, generate_password=True)

    body = deps["notifier"].sent[0].body
    password_line = next(line for line in body.splitlines() if "Contraseña inicial" in line)
    raw = password_line.split(":", 1)[1].strip()
    assert deps["password_hasher"].matches(
        raw, next(iter(deps["repository"].users.values())).password_hash
    )


def test_password_is_required_unless_generated(service):
    with pytest.raises(ValidationError) as error:
        create(service, password="")
    assert "password" in error.value.errors


def test_weak_password_is_rejected(service):
    with pytest.raises(ValidationError) as error:
        create(service, password="debil")
    assert "password" in error.value.errors


def test_duplicate_email_is_rejected_case_insensitively(service):
    create(service)
    with pytest.raises(DuplicateEmail) as error:
        create(service, email="MARTA@empresa.com")
    assert error.value.errors == {"email": [DUPLICATE_EMAIL_MESSAGE]}


def test_unknown_role_is_rejected(service):
    with pytest.raises(ValidationError) as error:
        create(service, role="ROOT")
    assert "role" in error.value.errors


def test_operator_cannot_manage_users(service):
    with pytest.raises(PermissionDeniedError):
        create(service, actor=OPERATOR)
    with pytest.raises(PermissionDeniedError):
        service.list_users(OPERATOR, UserFilters(), PageRequest())


def test_update_profile_and_role_with_audit_of_old_values(service, deps):
    view = create(service)

    updated = service.update_user(
        ADMIN, view.id, UpdateUserCommand("Marta Ruiz Gómez", "Contadora", "ADMIN")
    )

    assert (updated.full_name, updated.role, updated.email) == (
        "Marta Ruiz Gómez",
        "ADMIN",
        "marta@empresa.com",
    )
    record = deps["audit_logger"].records[-1]
    assert record.old_values["role"] == "OPERATOR" and record.new_values["role"] == "ADMIN"


def test_admin_cannot_change_own_role_or_deactivate_self(service, deps):
    me = create(service, email="yo@empresa.com", role="ADMIN")
    actor = Actor.for_role(RoleType.ADMIN, user_id=me.id)

    with pytest.raises(SelfManagementNotAllowed):
        service.update_user(actor, me.id, UpdateUserCommand("Yo", "Dueña", "OPERATOR"))
    with pytest.raises(SelfManagementNotAllowed):
        service.deactivate_user(actor, me.id)


def test_change_password_emails_user_and_publishes_event(service, deps):
    view = create(service)

    service.change_password(ADMIN, view.id, ChangePasswordCommand(password="Nueva#2026x"))

    assert deps["repository"].get_by_id(view.id).password_hash == "hashed:Nueva#2026x"
    assert "Nueva#2026x" in deps["notifier"].sent[-1].body
    assert deps["audit_logger"].records[-1].new_values == {"password": "changed"}
    assert isinstance(deps["events"].events[-1], UserPasswordChanged)


def test_deactivate_publishes_event_and_reactivate(service, deps):
    view = create(service)

    assert service.deactivate_user(ADMIN, view.id).status == "INACTIVE"
    assert deps["events"].events == [
        UserDeactivated(user_id=view.id, occurred_at=deps["events"].events[0].occurred_at)
    ]
    assert service.activate_user(ADMIN, view.id).status == "ACTIVE"


def test_unlock_clears_the_lock(service, deps):
    from datetime import UTC, datetime

    view = create(service)
    user = deps["repository"].get_by_id(view.id)
    for _ in range(3):
        user.register_failed_login(datetime.now(UTC))
    assert service.get_user(ADMIN, view.id).is_locked

    assert service.unlock_user(ADMIN, view.id).is_locked is False
    assert deps["audit_logger"].records[-1].reason == "Desbloqueo manual de la cuenta"
