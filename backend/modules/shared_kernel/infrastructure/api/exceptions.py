"""Translates errors into a single JSON error format for the whole API.

Every error response has the shape ``{"detail": "<message>", "errors": {"<field>": ["..."]}}``,
so the frontend can show a general message and mark the fields to correct (NFR-03-02).
"""

from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from modules.shared_kernel.domain.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

_STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (ValidationError, status.HTTP_400_BAD_REQUEST),
    (PermissionDeniedError, status.HTTP_403_FORBIDDEN),
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (DomainError, status.HTTP_400_BAD_REQUEST),
]


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        http_status = next(code for kind, code in _STATUS_BY_ERROR if isinstance(exc, kind))
        errors = exc.errors if isinstance(exc, ValidationError) else {}
        return Response({"detail": exc.message, "errors": errors}, status=http_status)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, DRFValidationError):
        data = response.data
        errors = data if isinstance(data, dict) else {"non_field_errors": data}
        response.data = {"detail": ValidationError.default_message, "errors": errors}
    elif isinstance(response.data, dict) and "detail" in response.data:
        response.data = {"detail": str(response.data["detail"]), "errors": {}}
    return response
