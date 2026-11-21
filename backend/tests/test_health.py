from unittest.mock import patch

import pytest
from django.test import Client

# Every API request runs inside a database transaction (ATOMIC_REQUESTS).
pytestmark = pytest.mark.django_db


def test_health_reports_ok_when_dependencies_are_up():
    with (
        patch("modules.shared_kernel.infrastructure.api.views._check_database", return_value=True),
        patch("modules.shared_kernel.infrastructure.api.views._check_redis", return_value=True),
    ):
        response = Client().get("/api/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


def test_health_reports_degraded_when_a_dependency_is_down():
    with (
        patch("modules.shared_kernel.infrastructure.api.views._check_database", return_value=True),
        patch("modules.shared_kernel.infrastructure.api.views._check_redis", return_value=False),
    ):
        response = Client().get("/api/health/")

    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "unavailable"
