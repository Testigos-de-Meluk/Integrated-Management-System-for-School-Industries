"""Events published by the user accounts module (Observer pattern)."""

from dataclasses import dataclass
from uuid import UUID

from modules.shared_kernel.domain.events import DomainEvent


@dataclass(frozen=True, slots=True, kw_only=True)
class UserDeactivated(DomainEvent):
    """FR-01-13: the authentication module reacts by closing the user's active sessions."""

    user_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UserPasswordChanged(DomainEvent):
    """Sessions opened with the old password are closed as a precaution."""

    user_id: UUID
