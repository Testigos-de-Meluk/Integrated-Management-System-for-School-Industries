from django.test import Client


def test_openapi_schema_is_generated():
    response = Client().get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "IMSI API"
    assert "/api/health/" in schema["paths"]


def test_swagger_ui_and_redoc_are_served():
    assert Client().get("/api/docs/").status_code == 200
    assert Client().get("/api/redoc/").status_code == 200
