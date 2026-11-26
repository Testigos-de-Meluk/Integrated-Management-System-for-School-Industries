"""Resolves the :class:`Actor` that executes a request.

The actor comes from the authenticated session: ``SessionJwtAuthentication`` validates the access
token and its session and sets ``request.user.actor``. Requests without a valid session are
rejected with 401 (deny by default).
"""

import ipaddress

from rest_framework.request import Request
from rest_framework.throttling import BaseThrottle

from modules.shared_kernel.domain.exceptions import AuthenticationError
from modules.shared_kernel.domain.security import Actor


def get_current_actor(request: Request) -> Actor:
    actor = getattr(request.user, "actor", None)
    if isinstance(actor, Actor):
        return actor
    raise AuthenticationError()


def client_ip(request: Request) -> str | None:
    """Source IP of the request (NFR-08-01), resolved exactly like the rate limits do: behind
    ``NUM_PROXIES`` trusted reverse proxies it is taken from ``X-Forwarded-For``; with 0 it is
    the direct connection address and a header the client sets is ignored. Anything that is not
    an IP address (a misconfigured proxy) is dropped: the audit column only accepts IPs."""
    candidate = BaseThrottle().get_ident(request)
    try:
        return str(ipaddress.ip_address(candidate)) if candidate else None
    except ValueError:
        return None
