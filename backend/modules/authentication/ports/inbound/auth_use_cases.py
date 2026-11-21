"""Inbound port of the Authentication module (FR-01-01 … FR-01-06, FR-01-14; US 1.1 … US 1.6).

Login is a two-step process:

1. ``login`` checks email and password and returns a short-lived *pre-authentication token*. It
   is not an access token: it only allows the next step (FR-01-01).
2. Either ``start_enrollment`` + ``confirm_enrollment`` (first login: link the authenticator app)
   or ``verify_code`` (every other login) open the session and return the real tokens.

Use cases whose failure must be persisted (a failed attempt counts towards the lockout and is
audited) return an :class:`Outcome` instead of raising, so the failure is not rolled back.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from modules.shared_kernel.domain.exceptions import DomainError
from modules.shared_kernel.domain.security import Actor


class LoginStep(StrEnum):
    VERIFY_CODE = "VERIFY_CODE"  # the account already has an authenticator: ask for the code
    ENROLL_AUTHENTICATOR = "ENROLL_AUTHENTICATOR"  # first login: link the authenticator (QR)


# --- Output DTOs ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoginChallenge:
    step: LoginStep
    pre_auth_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class EnrollmentView:
    qr_code: str  # data URI of an SVG image, ready for <img src=...>
    secret: str  # base32 key, for typing it manually (FR-01-02)
    account_name: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    full_name: str
    email: str
    role: str
    permissions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SessionTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str  # delivered to the browser only as an httpOnly cookie
    refresh_expires_at: datetime
    user: CurrentUser


@dataclass(frozen=True, slots=True)
class Outcome[T]:
    """Either a value or a business error that was already recorded (audit, attempt counter)."""

    value: T | None = None
    error: DomainError | None = None

    @classmethod
    def ok(cls, value: T) -> "Outcome[T]":
        return cls(value=value)

    @classmethod
    def fail(cls, error: DomainError) -> "Outcome[T]":
        return cls(error=error)


# --- Port -------------------------------------------------------------------------------------


class AuthUseCases(ABC):
    @abstractmethod
    def login(
        self, email: str, password: str, source_ip: str | None
    ) -> Outcome[LoginChallenge]: ...

    @abstractmethod
    def start_enrollment(self, pre_auth_token: str) -> EnrollmentView:
        """Generates (or regenerates) the QR code and secret, valid for 5 minutes."""

    @abstractmethod
    def confirm_enrollment(
        self, pre_auth_token: str, code: str, source_ip: str | None
    ) -> SessionTokens:
        """Confirms the link with a code from the app and opens the session."""

    @abstractmethod
    def verify_code(
        self, pre_auth_token: str, code: str, source_ip: str | None
    ) -> Outcome[SessionTokens]:
        """Second factor of every login. A wrong code counts towards the lockout."""

    @abstractmethod
    def refresh(self, refresh_token: str) -> Outcome[SessionTokens]:
        """New access token (and rotated refresh token) while the session is still active."""

    @abstractmethod
    def authenticate(self, access_token: str, source_ip: str | None) -> Actor:
        """Validates the access token and its session on every request; records activity."""

    @abstractmethod
    def current_user(self, actor: Actor) -> CurrentUser: ...

    @abstractmethod
    def logout(self, actor: Actor) -> None: ...

    @abstractmethod
    def terminate_sessions_for(self, user_id: UUID, reason: str) -> None:
        """Closes every active session of a user (deactivation, password change)."""
