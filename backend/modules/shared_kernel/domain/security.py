"""Fixed roles, permissions and the acting user (FR-01-04, RN-M1-01).

Permissions belong to roles, never to individual users. The role-permission matrix is the one in
``Workshops/Corrections/README.md`` section 4.4.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from .exceptions import PermissionDeniedError


class RoleType(StrEnum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"


class Permission(StrEnum):
    USER_MANAGE = "USER_MANAGE"
    BACKUP_MANAGE = "BACKUP_MANAGE"
    BACKUP_RESTORE = "BACKUP_RESTORE"
    CATALOG_VIEW = "CATALOG_VIEW"
    CATALOG_EDIT = "CATALOG_EDIT"
    CUSTOMER_MANAGE = "CUSTOMER_MANAGE"
    QUOTATION_MANAGE = "QUOTATION_MANAGE"
    EXPORT_QUEUE_MANAGE = "EXPORT_QUEUE_MANAGE"
    WORK_ORDER_MANAGE = "WORK_ORDER_MANAGE"
    AUDIT_LOG_VIEW = "AUDIT_LOG_VIEW"
    PRICE_HISTORY_IMPORT = "PRICE_HISTORY_IMPORT"


_OPERATOR_PERMISSIONS = frozenset(
    {
        Permission.CATALOG_VIEW,
        Permission.CUSTOMER_MANAGE,
        Permission.EXPORT_QUEUE_MANAGE,
        Permission.WORK_ORDER_MANAGE,
    }
)

#: Superadministrador and Administrador share the same permissions in the current scope.
DEFAULT_ROLE_PERMISSIONS: Mapping[RoleType, frozenset[Permission]] = {
    RoleType.SUPERADMIN: frozenset(Permission),
    RoleType.ADMIN: frozenset(Permission),
    RoleType.OPERATOR: _OPERATOR_PERMISSIONS,
}


@dataclass(frozen=True, slots=True)
class Actor:
    """Who is executing a use case, and from where (NFR-08-01 needs the source IP).

    ``user_id`` is ``None`` only for actors without an account (temporary development role).
    """

    role: RoleType
    permissions: frozenset[Permission]
    user_id: UUID | None = None
    source_ip: str | None = None
    session_id: UUID | None = None

    @classmethod
    def for_role(
        cls,
        role: RoleType,
        user_id: UUID | None = None,
        source_ip: str | None = None,
        session_id: UUID | None = None,
    ) -> "Actor":
        return cls(
            role=role,
            permissions=DEFAULT_ROLE_PERMISSIONS[role],
            user_id=user_id,
            source_ip=source_ip,
            session_id=session_id,
        )

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions

    def require(self, permission: Permission) -> None:
        """Deny by default: raise unless the role explicitly grants ``permission``."""
        if not self.has_permission(permission):
            raise PermissionDeniedError()
