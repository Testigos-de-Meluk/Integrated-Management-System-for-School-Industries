"""Inbound port of the User Accounts module (US 1.15 … US 1.23).

Only DTOs with plain values cross this boundary; the ``User`` entity never leaves the application.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from modules.shared_kernel.domain.pagination import Page, PageRequest
from modules.shared_kernel.domain.security import Actor, RoleType
from modules.user_accounts.domain.password_policy import MAX_LENGTH as PASSWORD_MAX_LENGTH
from modules.user_accounts.domain.user import (
    EMAIL_MAX_LENGTH,
    FULL_NAME_MAX_LENGTH,
    JOB_TITLE_MAX_LENGTH,
    AccountStatus,
)

#: Published for adapters, so they validate the same limits as the domain without importing it.
ROLES: tuple[str, ...] = tuple(role.value for role in RoleType)
ACCOUNT_STATUSES: tuple[str, ...] = tuple(status.value for status in AccountStatus)
__all__ = [
    "ACCOUNT_STATUSES",
    "EMAIL_MAX_LENGTH",
    "FULL_NAME_MAX_LENGTH",
    "JOB_TITLE_MAX_LENGTH",
    "PASSWORD_MAX_LENGTH",
    "ROLES",
    "ChangePasswordCommand",
    "CreateUserCommand",
    "UpdateUserCommand",
    "UserAccountUseCases",
    "UserFilters",
    "UserView",
]

# --- Input DTOs -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UserFilters:
    """All optional, combined with AND (US 1.16)."""

    name: str | None = None
    email: str | None = None
    job_title: str | None = None
    role: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    full_name: str
    email: str
    job_title: str
    role: str
    password: str | None = None  # ignored when generate_password is True
    generate_password: bool = False


@dataclass(frozen=True, slots=True)
class UpdateUserCommand:
    full_name: str
    job_title: str
    role: str


@dataclass(frozen=True, slots=True)
class ChangePasswordCommand:
    password: str | None = None
    generate_password: bool = False


# --- Output DTO -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UserView:
    id: UUID
    full_name: str
    email: str
    job_title: str
    role: str
    status: str
    last_access_at: datetime | None  # None = the user has never logged in (US 1.15.3)
    is_locked: bool
    locked_until: datetime | None


# --- Port -------------------------------------------------------------------------------------


class UserAccountUseCases(ABC):
    @abstractmethod
    def list_users(
        self, actor: Actor, filters: UserFilters, page_request: PageRequest
    ) -> Page[UserView]: ...

    @abstractmethod
    def get_user(self, actor: Actor, user_id: UUID) -> UserView: ...

    @abstractmethod
    def create_user(self, actor: Actor, command: CreateUserCommand) -> UserView:
        """Creates the account and emails the credentials to the new user (FR-01-11)."""

    @abstractmethod
    def update_user(self, actor: Actor, user_id: UUID, command: UpdateUserCommand) -> UserView:
        """Name, job title and role. The email can never change (FR-01-12)."""

    @abstractmethod
    def change_password(
        self, actor: Actor, user_id: UUID, command: ChangePasswordCommand
    ) -> UserView:
        """Sets a new password and emails it to the user (US 1.19)."""

    @abstractmethod
    def deactivate_user(self, actor: Actor, user_id: UUID) -> UserView: ...

    @abstractmethod
    def activate_user(self, actor: Actor, user_id: UUID) -> UserView: ...

    @abstractmethod
    def unlock_user(self, actor: Actor, user_id: UUID) -> UserView: ...
