"""Local development settings (used by Docker Compose)."""

from .base import *  # noqa: F403
from .base import env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)

# TEMPORARY: role chosen with the X-Dev-Role header until the authentication module exists.
DEV_ROLE_HEADER_ENABLED = env_bool("DEV_ROLE_HEADER_ENABLED", True)

# Local development runs over plain HTTP, so the refresh cookie cannot be "Secure".
REFRESH_COOKIE_SECURE = env_bool("REFRESH_COOKIE_SECURE", False)
