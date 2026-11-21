"""Inbound port used by OTHER MODULES (not by people): account checks needed to log in.

The authentication module never reads the user tables nor sees password hashes. It asks this
port to check credentials and to count failed attempts, so the lockout rules stay inside the user
accounts module (FR-01-14). There is no ``Actor`` here: these calls happen before anyone is
authenticated.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class CredentialCheckOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"  # unknown email or wrong password
    INACTIVE = "INACTIVE"  # correct password, deactivated account (US 1.1.7)
    LOCKED = "LOCKED"  # temporarily locked by failed attempts (FR-01-14)


@dataclass(frozen=True, slots=True)
class AccountSummary:
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class CredentialCheckResult:
    outcome: CredentialCheckOutcome
    account: AccountSummary | None = None  # None when the email does not exist
    locked_until: datetime | None = None
    locked_now: bool = False  # this attempt caused the lock


@dataclass(frozen=True, slots=True)
class FailedAttemptResult:
    locked_now: bool
    locked_until: datetime | None


class AccountAccess(ABC):
    @abstractmethod
    def check_credentials(self, email: str, raw_password: str) -> CredentialCheckResult:
        """Verifies email + password and counts a failure when the password is wrong."""

    @abstractmethod
    def register_failed_second_factor(self, user_id: UUID) -> FailedAttemptResult:
        """A wrong TOTP code counts towards the same lockout as a wrong password."""

    @abstractmethod
    def register_successful_login(self, user_id: UUID) -> None:
        """Resets the failure counter and records the last access (US 1.15)."""

    @abstractmethod
    def get_account(self, user_id: UUID) -> AccountSummary | None: ...

    @abstractmethod
    def is_locked(self, user_id: UUID) -> datetime | None:
        """Returns ``locked_until`` while the account is locked, otherwise ``None``."""
