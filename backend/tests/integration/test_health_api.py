from __future__ import annotations


def test_health_reports_db_and_jdk(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db"] == "ok"
    assert body["version"]
    # JDK обязателен для проекта: без него не работают сборка и запуск
    assert body["javac"] is not None, body
    assert body["status"] == "ok", body["problems"]
    assert response.headers["x-request-id"]


def test_unknown_route_uses_error_format(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"]


def test_openapi_is_served(client):
    schema = client.get("/api/openapi.json").json()
    assert "/api/health" in schema["paths"]
