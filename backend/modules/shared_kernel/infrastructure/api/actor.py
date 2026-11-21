"""Resolves the :class:`Actor` that executes a request.

TEMPORARY: until the authentication module exists, the role is taken from the ``X-Dev-Role``
header (``SUPERADMIN`` when absent). This is only possible when ``DEV_ROLE_HEADER_ENABLED`` is on
(development and tests). In any other environment every request is rejected, so this shortcut can
never reach production. The authentication module will replace this function with the role of the
JWT's user; views and use cases will not change.
"""

from django.conf import settings
from rest_framework.request import Request

from modules.shared_kernel.domain.exceptions import PermissionDeniedError, ValidationError
from modules.shared_kernel.domain.security import Actor, RoleType

DEV_ROLE_HEADER = "X-Dev-Role"


def get_current_actor(request: Request) -> Actor:
    if not getattr(settings, "DEV_ROLE_HEADER_ENABLED", False):
        raise PermissionDeniedError()

    raw_role = request.headers.get(DEV_ROLE_HEADER, RoleType.SUPERADMIN)
    try:
        role = RoleType(raw_role.upper())
    except ValueError as error:
        raise ValidationError.for_field(
            "role", f"Rol desconocido: {raw_role}. Use SUPERADMIN, ADMIN u OPERATOR."
        ) from error
    return Actor.for_role(role, source_ip=client_ip(request))


def client_ip(request: Request) -> str | None:
    """Source IP of the request (NFR-08-01). Behind the dev proxy this is the proxy's address;
    the production reverse proxy will forward the real one."""
    return request.META.get("REMOTE_ADDR") or None
