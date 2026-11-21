"""Use cases of the User Accounts module (implements ``UserAccountUseCases``).

Same steps as every module: permission → domain → repository → audit → output DTO. Some use cases
also notify the user by email and publish domain events for other modules.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from modules.shared_kernel.domain.audit import AuditAction, AuditRecord
from modules.shared_kernel.domain.exceptions import ValidationError
from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, Permission, RoleType
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger
from modules.shared_kernel.ports.outbound.event_publisher import EventPublisher
from modules.shared_kernel.ports.outbound.notifier import Notifier
from modules.shared_kernel.ports.outbound.password_hasher import PasswordHasher
from modules.user_accounts.domain.events import UserDeactivated, UserPasswordChanged
from modules.user_accounts.domain.exceptions import (
    DuplicateEmail,
    SelfManagementNotAllowed,
    UserNotFound,
)
from modules.user_accounts.domain.password_policy import PasswordPolicy
from modules.user_accounts.domain.user import User, normalize_email
from modules.user_accounts.ports.inbound.user_account_use_cases import (
    ChangePasswordCommand,
    CreateUserCommand,
    UpdateUserCommand,
    UserAccountUseCases,
    UserFilters,
    UserView,
)
from modules.user_accounts.ports.outbound.user_repository import UserRepository

from .emails import new_account_email, password_changed_email

ENTITY_TYPE = "User"
PASSWORD_REQUIRED = "Ingrese una contraseña o solicite una generada automáticamente."


def to_view(user: User, now: datetime) -> UserView:
    return UserView(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        job_title=user.job_title,
        role=user.role.value,
        status=user.status.value,
        last_access_at=user.last_access_at,
        is_locked=user.is_locked(now),
        locked_until=user.locked_until if user.is_locked(now) else None,
    )


def parse_role(raw: str) -> RoleType:
    try:
        return RoleType(raw)
    except ValueError as error:
        raise ValidationError.for_field(
            "role", "Seleccione un rol válido: Superadministrador, Administrador u Operador."
        ) from error


class UserAccountService(UserAccountUseCases):
    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
        notifier: Notifier,
        audit_logger: AuditLogger,
        events: EventPublisher,
        login_url: str,
        password_policy: PasswordPolicy | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._hasher = password_hasher
        self._notifier = notifier
        self._audit = audit_logger
        self._events = events
        self._login_url = login_url
        self._policy = password_policy or PasswordPolicy()
        self._now = clock

    # --- Queries ------------------------------------------------------------------------------

    def list_users(
        self, actor: Actor, filters: UserFilters, page_request: PageRequest
    ) -> Page[UserView]:
        actor.require(Permission.USER_MANAGE)
        page = self._repository.search(filters, page_request)
        now = self._now()
        return Page([to_view(u, now) for u in page.items], page.total, page.request)

    def get_user(self, actor: Actor, user_id: UUID) -> UserView:
        actor.require(Permission.USER_MANAGE)
        return to_view(self._get_or_fail(user_id), self._now())

    # --- Commands -----------------------------------------------------------------------------

    def create_user(self, actor: Actor, command: CreateUserCommand) -> UserView:
        actor.require(Permission.USER_MANAGE)
        role = parse_role(command.role)
        if self._repository.exists_with_email(normalize_email(command.email)):
            raise DuplicateEmail()
        raw_password = self._resolve_password(command.password, command.generate_password)

        user = User.register(
            command.full_name,
            command.email,
            command.job_title,
            role,
            self._hasher.hash(raw_password),
        )
        self._repository.add(user)
        self._log(AuditAction.CREATED, actor, user, old=None)
        self._notifier.send(
            new_account_email(
                to=user.email,
                full_name=user.full_name,
                role=user.role,
                password=raw_password,
                login_url=self._login_url,
            )
        )
        return to_view(user, self._now())

    def update_user(self, actor: Actor, user_id: UUID, command: UpdateUserCommand) -> UserView:
        actor.require(Permission.USER_MANAGE)
        user = self._get_or_fail(user_id)
        new_role = parse_role(command.role)
        if user.id == actor.user_id and new_role is not user.role:
            raise SelfManagementNotAllowed()

        before = user.snapshot()
        user.update_profile(command.full_name, command.job_title)
        user.change_role(new_role)  # applies on the user's next request (FR-01-12)
        self._repository.update(user)
        self._log(AuditAction.UPDATED, actor, user, old=before)
        return to_view(user, self._now())

    def change_password(
        self, actor: Actor, user_id: UUID, command: ChangePasswordCommand
    ) -> UserView:
        actor.require(Permission.USER_MANAGE)
        user = self._get_or_fail(user_id)
        raw_password = self._resolve_password(command.password, command.generate_password)

        user.change_password_hash(self._hasher.hash(raw_password))
        self._repository.update(user)
        self._audit.log(
            AuditRecord(
                action=AuditAction.UPDATED,
                entity_type=ENTITY_TYPE,
                entity_id=str(user.id),
                actor=actor,
                new_values={"password": "changed"},  # never the password or its hash
            )
        )
        self._events.publish(UserPasswordChanged(user_id=user.id))
        self._notifier.send(
            password_changed_email(
                to=user.email,
                full_name=user.full_name,
                password=raw_password,
                login_url=self._login_url,
            )
        )
        return to_view(user, self._now())

    def deactivate_user(self, actor: Actor, user_id: UUID) -> UserView:
        actor.require(Permission.USER_MANAGE)
        user = self._get_or_fail(user_id)
        if user.id == actor.user_id:
            raise SelfManagementNotAllowed()
        before = user.snapshot()
        user.deactivate()
        self._repository.update(user)
        self._log(AuditAction.STATUS_CHANGED, actor, user, old=before)
        self._events.publish(UserDeactivated(user_id=user.id))  # sessions are closed (FR-01-13)
        return to_view(user, self._now())

    def activate_user(self, actor: Actor, user_id: UUID) -> UserView:
        actor.require(Permission.USER_MANAGE)
        user = self._get_or_fail(user_id)
        before = user.snapshot()
        user.activate()
        self._repository.update(user)
        self._log(AuditAction.STATUS_CHANGED, actor, user, old=before)
        return to_view(user, self._now())

    def unlock_user(self, actor: Actor, user_id: UUID) -> UserView:
        actor.require(Permission.USER_MANAGE)
        user = self._get_or_fail(user_id)
        was_locked = user.is_locked(self._now())
        user.unlock()
        self._repository.update(user)
        self._audit.log(
            AuditRecord(
                action=AuditAction.UPDATED,
                entity_type=ENTITY_TYPE,
                entity_id=str(user.id),
                actor=actor,
                old_values={"locked": was_locked},
                new_values={"locked": False},
                reason="Desbloqueo manual de la cuenta",
            )
        )
        return to_view(user, self._now())

    # --- Helpers ------------------------------------------------------------------------------

    def _resolve_password(self, password: str | None, generate: bool) -> str:
        if generate:
            return self._policy.generate()
        if not password:
            raise ValidationError.for_field("password", PASSWORD_REQUIRED)
        self._policy.validate(password)
        return password

    def _get_or_fail(self, user_id: UUID) -> User:
        user = self._repository.get_by_id(user_id)
        if user is None:
            raise UserNotFound()
        return user

    def _log(self, action: AuditAction, actor: Actor, user: User, old: dict | None) -> None:
        self._audit.log(
            AuditRecord(
                action=action,
                entity_type=ENTITY_TYPE,
                entity_id=str(user.id),
                actor=actor,
                old_values=old,
                new_values=user.snapshot(),
            )
        )
