from modules.shared_kernel.domain.exceptions import ConflictError, NotFoundError, ValidationError


class QuotationNotFound(NotFoundError):
    default_message = "La cotización solicitada no existe."


class InvalidQuotationItems(ValidationError):
    """Empty request, unavailable products or invalid quantities (US 2.7.4, US 2.7.5)."""

    def __init__(self, message: str) -> None:
        super().__init__({"items": [message]}, message)


class QuotationLocked(ConflictError):
    """Approved and rejected quotations are immutable (US 2.27.4, US 2.29.6, FR-02-15)."""

    default_message = "La cotización está aprobada o rechazada y ya no se puede modificar."
    code = "QUOTATION_LOCKED"


class ApprovalIncomplete(ValidationError):
    """US 2.27.7 (new): every item needs a final unit price and the quotation a dispatch date."""
