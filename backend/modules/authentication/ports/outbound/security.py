"""Security ports of the Authentication module (class diagram, page 1)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class PreAuthPurpose(StrEnum):
    VERIFY_CODE = "VERIFY_CODE"
    ENROLL_AUTHENTICATOR = "ENROLL_AUTHENTICATOR"


@dataclass(frozen=True, slots=True)
class IssuedToken:
    value: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PreAuthClaims:
    user_id: UUID
    purpose: PreAuthPurpose


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: UUID
    session_id: UUID


@dataclass(frozen=True, slots=True)
class RefreshClaims:
    user_id: UUID
    session_id: UUID
    token_id: str


class TokenIssuer(ABC):
    """Issues and reads signed tokens. ``read_*`` return ``None`` for invalid or expired tokens."""

    @abstractmethod
    def issue_pre_auth(
        self, user_id: UUID, purpose: PreAuthPurpose, now: datetime
    ) -> IssuedToken: ...

    @abstractmethod
    def read_pre_auth(self, token: str) -> PreAuthClaims | None: ...

    @abstractmethod
    def issue_access(self, user_id: UUID, session_id: UUID, now: datetime) -> IssuedToken: ...

    @abstractmethod
    def read_access(self, token: str) -> AccessClaims | None: ...

    @abstractmethod
    def issue_refresh(
        self, user_id: UUID, session_id: UUID, token_id: str, now: datetime
    ) -> IssuedToken: ...

    @abstractmethod
    def read_refresh(self, token: str) -> RefreshClaims | None: ...


class TwoFactorProvider(ABC):
    """Time-based one-time passwords (TOTP, RFC 6238) and their QR code."""

    @abstractmethod
    def new_secret(self) -> str: ...

    @abstractmethod
    def qr_code(self, secret: str, account_name: str) -> str:
        """Image (data URI) that authenticator apps scan to add the account."""

    @abstractmethod
    def matching_step(self, secret: str, code: str, now: datetime) -> int | None:
        """Time step of ``code`` if it is valid now (±30 s of clock drift), otherwise ``None``."""
