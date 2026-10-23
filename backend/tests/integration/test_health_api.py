from __future__ import annotations

import pytest

from engine.runtime.jdk import JdkInfo


def _fake_jdk(monkeypatch, info: JdkInfo) -> None:
    monkeypatch.setattr("app.api.health.detect_jdk", lambda _java_home=None: info)


def test_health_reports_db_and_version(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db"] == "ok"
    assert body["version"]
    assert body["status"] in {"ok", "degraded"}
    assert response.headers["x-request-id"]


def test_health_ok_with_supported_jdk(client, monkeypatch):
    _fake_jdk(monkeypatch, JdkInfo(javac="21.0.4", java="21.0.4", major=21))
    body = client.get("/api/health").json()
    assert body["status"] == "ok", body["problems"]
    assert body["javac"] == "21.0.4"


def test_health_degraded_on_old_jdk(client, monkeypatch):
    _fake_jdk(monkeypatch, JdkInfo(javac="17.0.20.1", java="17.0.20.1", major=17))
    body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert any("21" in problem for problem in body["problems"])


def test_health_degraded_without_javac(client, monkeypatch):
    _fake_jdk(monkeypatch, JdkInfo(javac=None, java=None, major=None))
    body = client.get("/api/health").json()
    assert body["status"] == "degraded"
    assert body["javac"] is None
    assert any("javac" in problem for problem in body["problems"])


@pytest.mark.jdk
def test_health_ok_with_installed_jdk(client):
    """Реальное окружение: JDK обязателен для сборки и запуска (джоб CI с JDK 21)."""
    body = client.get("/api/health").json()
    assert body["javac"] is not None, body
    assert body["status"] == "ok", body["problems"]


def test_unknown_route_uses_error_format(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"]


def test_openapi_is_served(client):
    schema = client.get("/api/openapi.json").json()
    assert "/api/health" in schema["paths"]
