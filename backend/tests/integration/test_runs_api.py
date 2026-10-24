"""Сборка и запуск через API на реальном JDK (S3.4–S3.6, метка `jdk`).

Локально: ``JB_JAVA_HOME=<JDK> uv run pytest -m jdk``; в CI JDK берётся из PATH.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from tests.integration.conftest import read_sse, wait_run

pytestmark = pytest.mark.jdk

SAMPLES = Path(__file__).resolve().parents[3] / "samples"


def program(body: str, imports: str = "") -> dict[str, str]:
    return {
        "Main.java": (
            f"{imports}\npublic class Main {{\n"
            f"    public static void main(String[] args) throws Exception {{\n{body}\n    }}\n}}\n"
        )
    }


def run(client, project, **body) -> dict:
    response = client.post(f"/api/projects/{project['id']}/runs", json={"kind": "run", **body})
    assert response.status_code == 202, response.text
    return wait_run(client, response.json()["run_id"], 60)


def only_item(info: dict) -> dict:
    [item] = info["items"]
    return item


# --- сборка --------------------------------------------------------------------------------------


def test_build_ok_then_cached(client, make_project):
    project = make_project(program('System.out.println("a");'))
    url = f"/api/projects/{project['id']}/build"
    first = client.post(url, json={}).json()
    assert first["ok"] is True
    assert [d for d in first["diagnostics"] if d["severity"] == "error"] == []
    assert first["duration_ms"] >= 0
    second = client.post(url, json={}).json()
    assert second["ok"] is True
    assert second["cached"] is True


def test_build_errors_are_mapped_to_lines_and_graph_nodes(client, make_project):
    files = program('int x = "text";\n        System.out.println(x);')
    project = make_project(files)
    result = client.post(f"/api/projects/{project['id']}/build", json={}).json()
    assert result["ok"] is False
    [error] = [d for d in result["diagnostics"] if d["severity"] == "error"]
    assert error["file"] == "Main.java"
    assert error["line"] == 4
    assert "incompatible types" in error["message"]
    assert error["node_id"].startswith("Main.java#Main.main(String[])")


def test_build_of_an_older_version_and_unknown_version(client, make_project):
    project = make_project(program('System.out.println("ok");'))
    broken = program("int x = ;")["Main.java"]
    client.put(
        f"/api/projects/{project['id']}/files/Main.java",
        json={"base_version_id": project["head_version_id"], "content": broken},
    )
    url = f"/api/projects/{project['id']}/build"
    assert client.post(url, json={}).json()["ok"] is False
    assert (
        client.post(url, json={"version_id": project["original_version_id"]}).json()["ok"] is True
    )
    assert client.post(url, json={"version_id": 9999}).status_code == 404


# --- запуск --------------------------------------------------------------------------------------


def test_run_prints_output_and_streams_events(client, make_project):
    project = make_project(program('System.out.println("Привет, мир!");'))
    info = run(client, project)
    assert info["status"] == "done"
    assert info["version_id"] == project["head_version_id"]
    item = only_item(info)
    assert (item["verdict"], item["exit_code"], item["stdout"]) == ("PASS", 0, "Привет, мир!\n")
    assert info["summary"]["passed"] == 1
    assert info["started_at"] and info["finished_at"]

    events = read_sse(client, info["id"])
    kinds = [e["event"] for e in events]
    assert kinds[0] == "status" and events[0]["data"]["status"] == "queued"
    assert kinds[-1] == "done"
    assert kinds.index("item") < kinds.index("result")
    stdout = "".join(
        e["data"]["text"] for e in events if e["event"] == "log" and e["data"]["stream"] == "stdout"
    )
    assert stdout == "Привет, мир!\n"


def test_stdin_and_args_reach_the_program(client, make_project):
    body = (
        '        var in = new java.util.Scanner(System.in, "UTF-8");\n'
        '        System.out.println(in.nextLine().toUpperCase() + " " + String.join(",", args));'
    )
    project = make_project(program(body))
    info = run(client, project, stdin="hello\n", args=["a", "b"])
    assert only_item(info)["stdout"] == "HELLO a,b\n"


def test_non_zero_exit_code_and_uncaught_exception_fail_the_item(client, make_project):
    exit_info = run(client, make_project(program("System.exit(3);")))
    assert exit_info["status"] == "done"
    assert (only_item(exit_info)["verdict"], only_item(exit_info)["exit_code"]) == ("FAIL", 3)

    crash = run(client, make_project(program('throw new IllegalStateException("boom");')))
    assert crash["status"] == "done"
    assert only_item(crash)["verdict"] == "FAIL"
    assert only_item(crash)["exit_code"] == 1
    assert crash["summary"]["data"]["exception"]["type"] == "java.lang.IllegalStateException"
    assert crash["summary"]["data"]["exception"]["message"] == "boom"


def test_timeout_comes_from_project_settings(client, make_project):
    project = make_project(program("while (true) { }"))
    client.patch(f"/api/projects/{project['id']}", json={"settings": {"run_timeout_s": 1}})
    started = time.monotonic()
    info = run(client, project)
    assert only_item(info)["verdict"] == "TIMEOUT"
    assert time.monotonic() - started < 15
    assert "время" in info["summary"]["message"]


def test_cancel_kills_a_running_program(client, make_project):
    project = make_project(program("Thread.sleep(60000);"))
    response = client.post(f"/api/projects/{project['id']}/runs", json={"kind": "run"})
    run_id = response.json()["run_id"]
    deadline = time.monotonic() + 30
    while client.get(f"/api/runs/{run_id}").json()["status"] != "running":
        assert time.monotonic() < deadline
        time.sleep(0.05)
    time.sleep(0.5)  # дать JVM стартовать

    started = time.monotonic()
    cancelled = client.post(f"/api/runs/{run_id}/cancel").json()
    assert cancelled["status"] == "cancelled"
    assert time.monotonic() - started < 10
    assert read_sse(client, run_id)[-1]["event"] == "done"


def test_compile_error_fails_the_run_with_diagnostics(client, make_project):
    project = make_project(program("System.out.println(undefined);"))
    info = run(client, project)
    assert info["status"] == "failed"
    assert info["items"] == []
    assert info["summary"]["data"]["stage"] == "compile"
    [error] = [d for d in info["summary"]["data"]["diagnostics"] if d["severity"] == "error"]
    assert error["line"] == 4

    events = read_sse(client, info["id"])
    assert [e["data"]["code"] for e in events if e["event"] == "error"] == ["COMPILE_ERROR"]
    assert any(e["event"] == "log" and e["data"]["stream"] == "build" for e in events)


def test_run_without_main_class_is_rejected_up_front(client, make_project):
    project = make_project({"A.java": "class A {}"})
    response = client.post(f"/api/projects/{project['id']}/runs", json={"kind": "run"})
    assert response.status_code == 400


def test_run_uses_the_requested_version(client, make_project):
    project = make_project(program('System.out.println("old");'))
    new_source = program('System.out.println("new");')["Main.java"]
    client.put(
        f"/api/projects/{project['id']}/files/Main.java",
        json={"base_version_id": project["head_version_id"], "content": new_source},
    )
    assert only_item(run(client, project))["stdout"] == "new\n"
    old = run(client, project, version_id=project["original_version_id"])
    assert only_item(old)["stdout"] == "old\n"
    assert old["version_id"] == project["original_version_id"]


def test_several_runs_in_parallel_do_not_mix_up_output(client, make_project):
    project = make_project(program("System.out.println(args[0]);"))
    ids = [
        client.post(
            f"/api/projects/{project['id']}/runs", json={"kind": "run", "args": [str(i)]}
        ).json()["run_id"]
        for i in range(6)
    ]
    outputs = [only_item(wait_run(client, run_id, 90))["stdout"] for run_id in ids]
    assert outputs == [f"{i}\n" for i in range(6)]


# --- сквозной сценарий: импорт → граф → запуск → вывод ---------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("scenario", ["single-order", "cyrillic", "uncaught-exception"])
def test_demo_orders_end_to_end_matches_the_golden_output(client, demo_orders, scenario):
    pid = demo_orders["id"]
    assert client.get(f"/api/projects/{pid}/structure").status_code == 200
    flow_ids = [
        n["method_id"]
        for n in client.get(f"/api/projects/{pid}/structure").json()["nodes"]
        if n["method_id"]
    ]
    assert (
        client.get(f"/api/projects/{pid}/flow", params={"method_id": flow_ids[0]}).status_code
        == 200
    )

    expected = json.loads(
        (SAMPLES / "demo-orders" / "scenarios" / f"{scenario}.json").read_text(encoding="utf-8")
    )
    info = run(client, demo_orders, stdin=expected["stdin"], args=expected["args"])
    item = only_item(info)
    # эталон корпуса нормализован: LF и без хвостовых переводов строки (samples/README.md)
    assert item["stdout"].rstrip("\n") == expected["expected_stdout"]
    assert "\r" not in item["stdout"]
    assert item["exit_code"] == expected.get("expected_exit_code", 0)
