from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

HELLO = {
    "Main.java": (
        "public class Main {\n"
        "    public static void main(String[] args) {\n"
        '        System.out.println("hi");\n'
        "    }\n"
        "}\n"
    )
}

Files = dict[str, str]
Make = Callable[..., dict[str, Any]]


@pytest.fixture
def make_project(client: TestClient) -> Make:
    """Создаёт проект из файлов через JSON-вариант ``POST /projects``; возвращает тело ответа."""

    def make(files: Files | None = None, name: str = "demo") -> dict[str, Any]:
        body = {
            "name": name,
            "files": [{"path": p, "content": c} for p, c in (files or HELLO).items()],
        }
        response = client.post("/api/projects", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return make


@pytest.fixture
def demo_orders(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/projects", json={"sample_id": "demo-orders"})
    assert response.status_code == 201, response.text
    return response.json()


def wait_run(client: TestClient, run_id: int, timeout_s: float = 60.0) -> dict[str, Any]:
    """Ждёт завершения запуска (опрос ``GET /runs/{id}``)."""
    deadline = time.monotonic() + timeout_s
    while True:
        info = client.get(f"/api/runs/{run_id}").json()
        if info["status"] not in {"queued", "running"}:
            return info
        assert time.monotonic() < deadline, f"запуск {run_id} не завершился: {info}"
        time.sleep(0.05)


def read_sse(client: TestClient, run_id: int, headers: dict[str, str] | None = None) -> list[dict]:
    """События SSE запуска: ``[{event, data, id}]`` (поток закрывается после ``done``)."""
    import json

    events: list[dict] = []
    current: dict[str, Any] = {}
    with client.stream("GET", f"/api/runs/{run_id}/events", headers=headers or {}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line == "":
                if current:
                    events.append(current)
                    current = {}
            elif line.startswith(":"):
                continue
            else:
                key, _, value = line.partition(":")
                value = value.lstrip(" ")
                current[key] = json.loads(value) if key == "data" else value
    if current:
        events.append(current)
    return events
