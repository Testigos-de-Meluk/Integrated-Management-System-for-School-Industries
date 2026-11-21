"""Resolves the :class:`Actor` that executes a request.

The actor comes from the authenticated session (``SessionJwtAuthentication`` sets
``request.user.actor``). Requests without a valid session are rejected: deny by default.

TEMPORARY (removed when the frontend has its login screens): in development and tests, an explicit
``X-Dev-Role`` header still selects a role without logging in. It only works while
``DEV_ROLE_HEADER_ENABLED`` is on, so it can never reach production.
"""

from django.conf import settings
from rest_framework.request import Request

from modules.shared_kernel.domain.exceptions import AuthenticationError, ValidationError
from modules.shared_kernel.domain.security import Actor, RoleType

DEV_ROLE_HEADER = "X-Dev-Role"


def get_current_actor(request: Request) -> Actor:
    actor = getattr(request.user, "actor", None)
    if isinstance(actor, Actor):
        return actor

    raw_role = request.headers.get(DEV_ROLE_HEADER)
    if raw_role and getattr(settings, "DEV_ROLE_HEADER_ENABLED", False):
        try:
            role = RoleType(raw_role.upper())
        except ValueError as error:
            raise ValidationError.for_field(
                "role", f"Rol desconocido: {raw_role}. Use SUPERADMIN, ADMIN u OPERATOR."
            ) from error
        return Actor.for_role(role, source_ip=client_ip(request))

    raise AuthenticationError()


def client_ip(request: Request) -> str | None:
    """Source IP of the request (NFR-08-01). Behind the dev proxy this is the proxy's address;
    the production reverse proxy will forward the real one."""
    return request.META.get("REMOTE_ADDR") or None
