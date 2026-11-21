"""Audit log vocabulary (NFR-08-01, RN-M1-05).

Use cases describe *what* happened with an :class:`AuditRecord`; the ``AuditLogger`` outbound port
decides *where* it is stored. The insert-only database implementation arrives with the
authentication module.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .security import Actor


class AuditAction(StrEnum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPORTED = "EXPORTED"
    DELETED = "DELETED"
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    LOGOUT = "LOGOUT"
    BACKUP = "BACKUP"
    RESTORED = "RESTORED"


class ActorType(StrEnum):
    USER = "USER"  # a person with an account
    SYSTEM = "SYSTEM"  # scheduled jobs, management commands
    ANONYMOUS = "ANONYMOUS"  # public assistant, failed login with an unknown email


class OperationResult(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


@dataclass(frozen=True, slots=True)
class AuditRecord:
    action: AuditAction
    entity_type: str
    entity_id: str
    actor: Actor | None
    old_values: Mapping[str, Any] | None = None
    new_values: Mapping[str, Any] | None = None
    reason: str | None = None
    result: OperationResult = OperationResult.SUCCESS
    #: Set explicitly for SYSTEM / ANONYMOUS actions; derived from ``actor`` otherwise.
    actor_type: ActorType | None = None
    #: Human-readable actor when there is no account (e.g. "create_superadmin", an email).
    actor_label: str | None = None
    #: Source IP when there is no ``actor`` (e.g. a failed login).
    source_ip: str | None = None

    @property
    def resolved_actor_type(self) -> ActorType:
        if self.actor_type is not None:
            return self.actor_type
        if self.actor is not None and self.actor.user_id is not None:
            return ActorType.USER
        return ActorType.ANONYMOUS

    @property
    def resolved_source_ip(self) -> str | None:
        return self.source_ip or (self.actor.source_ip if self.actor else None)

    @property
    def resolved_actor_label(self) -> str | None:
        if self.actor_label:
            return self.actor_label
        return self.actor.role.value if self.actor else None
