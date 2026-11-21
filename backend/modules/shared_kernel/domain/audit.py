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
