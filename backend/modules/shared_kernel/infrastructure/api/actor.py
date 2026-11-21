"""Resolves the :class:`Actor` that executes a request.

The actor comes from the authenticated session: ``SessionJwtAuthentication`` validates the access
token and its session and sets ``request.user.actor``. Requests without a valid session are
rejected with 401 (deny by default).
"""

from rest_framework.request import Request

from modules.shared_kernel.domain.exceptions import AuthenticationError
from modules.shared_kernel.domain.security import Actor


def get_current_actor(request: Request) -> Actor:
    actor = getattr(request.user, "actor", None)
    if isinstance(actor, Actor):
        return actor
    raise AuthenticationError()


def client_ip(request: Request) -> str | None:
    """Source IP of the request (NFR-08-01). Behind the dev proxy this is the proxy's address;
    the production reverse proxy will forward the real one."""
    return request.META.get("REMOTE_ADDR") or None
