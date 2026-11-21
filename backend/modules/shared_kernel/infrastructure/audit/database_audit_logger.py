import json
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder

from modules.shared_kernel.domain.audit import AuditRecord
from modules.shared_kernel.infrastructure.models import AuditEntryModel
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger


def _json_safe(values: Any) -> Any:
    """UUIDs, dates and enums become plain JSON values."""
    if values is None:
        return None
    return json.loads(json.dumps(dict(values), cls=DjangoJSONEncoder))


class DatabaseAuditLogger(AuditLogger):
    """Writes audit records to the insert-only ``audit_entry`` table.

    It runs inside the request's transaction: if the business change rolls back, its audit entry
    does too, and if the audit entry cannot be written, the business change is not committed.
    """

    def log(self, record: AuditRecord) -> None:
        AuditEntryModel.objects.create(
            actor_type=record.resolved_actor_type.value,
            user_id=record.actor.user_id if record.actor else None,
            actor_label=record.resolved_actor_label or "",
            source_ip=record.resolved_source_ip,
            action=record.action.value,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            old_values=_json_safe(record.old_values),
            new_values=_json_safe(record.new_values),
            reason=record.reason or "",
            result=record.result.value,
        )
