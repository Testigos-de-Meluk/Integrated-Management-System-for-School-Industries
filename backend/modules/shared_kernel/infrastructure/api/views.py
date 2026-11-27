"""Technical endpoints shared by the whole system."""

import redis
from django.conf import settings
from django.db import connection
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from modules.shared_kernel.domain.business_days import colombian_holidays
from modules.shared_kernel.infrastructure.api.actor import get_current_actor


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


_HEALTH_RESPONSE = inline_serializer(
    name="HealthResponse",
    fields={
        "status": serializers.ChoiceField(choices=["ok", "degraded"]),
        "checks": serializers.DictField(child=serializers.ChoiceField(["ok", "unavailable"])),
    },
)


@extend_schema(
    tags=["system"],
    summary="Health check",
    responses={
        200: OpenApiResponse(_HEALTH_RESPONSE, description="API, database and Redis are up."),
        503: OpenApiResponse(_HEALTH_RESPONSE, description="A dependency is unavailable."),
    },
)
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


class HolidayQuerySerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)


_HOLIDAYS_RESPONSE = inline_serializer(
    name="HolidaysResponse",
    fields={
        "year": serializers.IntegerField(),
        "holidays": serializers.ListField(child=serializers.DateField()),
    },
)


@extend_schema(
    tags=["system"],
    summary="Colombian public holidays of a year (business days are Monday to Friday minus these)",
    parameters=[HolidayQuerySerializer],
    responses=_HOLIDAYS_RESPONSE,
)
@api_view(["GET"])
def holidays(request: Request) -> Response:
    get_current_actor(request)  # any signed-in user: the screens warn about non-business days
    query = HolidayQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    year = query.validated_data["year"]
    return Response({"year": year, "holidays": sorted(colombian_holidays(year))})
