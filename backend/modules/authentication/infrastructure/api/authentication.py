"""DRF authentication for every API request: ``Authorization: Bearer <access token>``."""

from dataclasses import dataclass

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.request import Request

from modules.authentication.infrastructure.dependencies import auth_use_cases
from modules.shared_kernel.domain.security import Actor
from modules.shared_kernel.infrastructure.api.actor import client_ip


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """What ``request.user`` holds once the access token and its session are valid."""

    actor: Actor
    is_authenticated: bool = True


class SessionJwtAuthentication(BaseAuthentication):
    keyword = b"bearer"

    def authenticate(self, request: Request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword:
            return None  # no token: anonymous (use cases then deny by default)
        if len(parts) != 2:
            return None
        token = parts[1].decode("ascii", errors="ignore")
        # Raises SessionExpired / SessionReplaced / AccountInactive… → 401 with a clear message.
        actor = auth_use_cases().authenticate(token, client_ip(request))
        return AuthenticatedPrincipal(actor), token

    def authenticate_header(self, request: Request) -> str:
        return 'Bearer realm="imsi"'


class SessionJwtAuthenticationScheme(OpenApiAuthenticationExtension):
    """Shows the "Authorize" button in Swagger UI."""

    target_class = (
        "modules.authentication.infrastructure.api.authentication.SessionJwtAuthentication"
    )
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
