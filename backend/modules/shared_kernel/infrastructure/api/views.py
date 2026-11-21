"""Technical endpoints shared by the whole system."""

import redis
from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response


def _check_database() -> bool:
    try:
        connection.ensure_connection()
        return True
    except Exception:
        return False


def _check_redis() -> bool:
    try:
        return bool(redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2).ping())
    except Exception:
        return False


@api_view(["GET"])
def health(request: Request) -> Response:
    """Report whether the API, the database and Redis are reachable."""
    checks = {"database": _check_database(), "redis": _check_redis()}
    healthy = all(checks.values())
    return Response(
        {
            "status": "ok" if healthy else "degraded",
            "checks": {name: "ok" if ok else "unavailable" for name, ok in checks.items()},
        },
        status=200 if healthy else 503,
    )
