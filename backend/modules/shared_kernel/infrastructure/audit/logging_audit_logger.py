import json
import logging

from modules.shared_kernel.domain.audit import AuditRecord
from modules.shared_kernel.ports.outbound.audit_logger import AuditLogger

logger = logging.getLogger("imsi.audit")


class LoggingAuditLogger(AuditLogger):
    """Temporary adapter: writes audit records to the application log.

    It will be replaced by the insert-only ``DatabaseAuditLogger`` (table ``AUDIT_ENTRY``) when the
    authentication module is implemented. Use cases do not change: they only know the port.
    """

    def log(self, record: AuditRecord) -> None:
        logger.info(
            "%s %s %s by %s %s",
            record.action,
            record.entity_type,
            record.entity_id,
            record.actor.role if record.actor else "ANONYMOUS",
            json.dumps(
                {
                    "old": record.old_values,
                    "new": record.new_values,
                    "reason": record.reason,
                    "result": record.result,
                },
                default=str,
                ensure_ascii=False,
            ),
        )
