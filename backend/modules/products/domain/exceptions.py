from modules.shared_kernel.domain.exceptions import ConflictError, NotFoundError, ValidationError

DUPLICATE_CODE_MESSAGE = "El código de producto ya se encuentra registrado en el catálogo"


class ProductNotFound(NotFoundError):
    default_message = "El producto solicitado no existe."


class DuplicateProductCode(ValidationError):
    """FR-02-02: the product code must be unique."""

    def __init__(self) -> None:
        super().__init__({"code": [DUPLICATE_CODE_MESSAGE]}, DUPLICATE_CODE_MESSAGE)


class InvalidProductStatusChange(ConflictError):
    default_message = "El cambio de estado solicitado no es válido."
