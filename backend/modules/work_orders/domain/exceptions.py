from modules.shared_kernel.domain.exceptions import ConflictError, NotFoundError, ValidationError


class WorkOrderNotFound(NotFoundError):
    default_message = "La orden de trabajo no existe."


class WorkOrderNotEditable(ConflictError):
    default_message = (
        "Solo se puede editar una orden de trabajo en estado Pendiente: "
        "una vez exportada a Odoo ya no se modifica."
    )
    code = "WORK_ORDER_NOT_EDITABLE"


class InvalidWorkOrderTransition(ConflictError):
    code = "INVALID_WORK_ORDER_TRANSITION"


class ActiveWorkOrderExists(ConflictError):
    code = "ACTIVE_WORK_ORDER_EXISTS"

    def __init__(self, number: str | None = None) -> None:
        detail = f" ({number})" if number else ""
        super().__init__(
            f"Esta cotización ya tiene una orden de trabajo activa{detail}. "
            "Solo se puede generar otra si la anterior está anulada."
        )


class InvalidWorkOrderItems(ValidationError):
    pass


class WorkOrdersNotPending(ConflictError):
    """Exporting O.T.s that someone else exported or annulled meanwhile (step 5d)."""

    code = "WORK_ORDERS_NOT_PENDING"

    def __init__(self, numbers: list[str]) -> None:
        self.numbers = numbers
        listed = ", ".join(numbers)
        super().__init__(
            "Estas órdenes de trabajo ya no están pendientes de exportar (otra persona las exportó "
            f"o fueron anuladas): {listed}. Actualice la lista y vuelva a intentarlo."
        )
