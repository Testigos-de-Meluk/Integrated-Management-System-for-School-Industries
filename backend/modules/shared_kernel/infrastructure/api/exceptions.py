"""Translates errors into a single JSON error format for the whole API.

Every error response has the shape ``{"detail": "<message>", "errors": {"<field>": ["..."]}}``,
so the frontend can show a general message and mark the fields to correct (NFR-03-02).
"""

from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from modules.shared_kernel.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationError,
)

_STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (ValidationError, status.HTTP_400_BAD_REQUEST),
    (AuthenticationError, status.HTTP_401_UNAUTHORIZED),
    (PermissionDeniedError, status.HTTP_403_FORBIDDEN),
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (ServiceUnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE),
    (DomainError, status.HTTP_400_BAD_REQUEST),
]


def error_response(exc: DomainError) -> Response:
    """Builds the standard error response without raising.

    Use cases whose failures must be persisted (failed logins count towards the lockout and are
    audited) return the error instead of raising it: raising would roll back the request's
    transaction and erase that record.
    """
    http_status = next(code for kind, code in _STATUS_BY_ERROR if isinstance(exc, kind))
    body = {"detail": exc.message, "errors": exc.errors if isinstance(exc, ValidationError) else {}}
    if exc.code:
        body["code"] = exc.code
    return Response(body, status=http_status)


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return error_response(exc)

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
