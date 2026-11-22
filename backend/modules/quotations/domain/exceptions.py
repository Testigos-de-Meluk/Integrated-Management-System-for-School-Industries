from modules.shared_kernel.domain.exceptions import NotFoundError, ValidationError


class QuotationNotFound(NotFoundError):
    default_message = "La cotización solicitada no existe."


class InvalidQuotationItems(ValidationError):
    """Empty request, unavailable products or invalid quantities (US 2.7.4, US 2.7.5)."""

    def __init__(self, message: str) -> None:
        super().__init__({"items": [message]}, message)
