"""Граф через API (S3.7, docs/08-api.md § 4): структура, блок-схема, дерево, узлы, позиция."""

from __future__ import annotations

from urllib.parse import quote

import pytest

from app.main import create_app


@pytest.fixture
def pid(demo_orders) -> int:
    return demo_orders["id"]


def structure(client, pid, **params):
    response = client.get(f"/api/projects/{pid}/structure", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_structure_modes_on_demo_orders(client, pid, demo_orders):
    methods = structure(client, pid)
    assert methods["mode"] == "methods"
    assert methods["version_id"] == demo_orders["head_version_id"]
    assert len(methods["content_hash"]) == 64
    kinds = {n["kind"] for n in methods["nodes"]}
    assert {"class", "method"} <= kinds
    assert {e["kind"] for e in methods["edges"]} >= {"contains", "calls"}

    types = structure(client, pid, mode="types")
    assert all(n["node_type"] == "type" for n in types["nodes"])

    deps = structure(client, pid, mode="deps")
    assert deps["mode"] == "deps"


def test_structure_rejects_unknown_mode_and_version(client, pid):
    assert client.get(f"/api/projects/{pid}/structure", params={"mode": "huge"}).status_code == 400
    assert (
        client.get(f"/api/projects/{pid}/structure", params={"version_id": 9999}).status_code == 404
    )


def flowable(client, pid) -> list[str]:
    return [n["method_id"] for n in structure(client, pid)["nodes"] if n["method_id"]]


def test_flow_of_every_method_is_served(client, pid, demo_orders):
    ids = flowable(client, pid)
    assert len(ids) > 20
    for method_id in ids[:15]:
        response = client.get(f"/api/projects/{pid}/flow", params={"method_id": method_id})
        assert response.status_code == 200, (method_id, response.text)
        flow = response.json()
        assert flow["method_id"] == method_id
        assert flow["version_id"] == demo_orders["head_version_id"]
        assert flow["entry"] in {n["id"] for n in flow["nodes"]}
        node_ids = {n["id"] for n in flow["nodes"]}
        # ребро ``call`` ведёт в другой метод проекта, остальные — внутри схемы метода
        local = [e for e in flow["edges"] if e["kind"] != "call"]
        assert all(e["source"] in node_ids and e["target"] in node_ids for e in local)


def test_unknown_method_is_404(client, pid):
    response = client.get(
        f"/api/projects/{pid}/flow", params={"method_id": "Main.java#Main.nope()"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert client.get(f"/api/projects/{pid}/flow").status_code == 400  # method_id обязателен


def test_tree_has_files_types_and_members(client, pid):
    tree = client.get(f"/api/projects/{pid}/tree").json()
    assert tree["roots"]

    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node["children"])

    kinds = {n["kind"] for n in walk(tree["roots"])}
    assert {"file", "type", "member"} <= kinds


def first_flow_node(client, pid) -> tuple[str, dict]:
    for method_id in flowable(client, pid):
        flow = client.get(f"/api/projects/{pid}/flow", params={"method_id": method_id}).json()
        inner = [n for n in flow["nodes"] if n["id"] != method_id and "/" in n["id"]]
        if inner:
            return method_id, inner[0]
    raise AssertionError("в демо нет метода с блоками")


def test_node_details_by_path_and_by_lookup(client, pid):
    method_id, node = first_flow_node(client, pid)
    url = f"/api/projects/{pid}/nodes/{quote(node['id'], safe='/')}"
    by_path = client.get(url)
    assert by_path.status_code == 200, by_path.text
    details = by_path.json()
    assert details["node_id"] == node["id"]
    assert details["kind"] == node["kind"]
    assert details["range"] == node["range"]

    looked_up = client.post(f"/api/projects/{pid}/nodes/lookup", json={"node_id": node["id"]})
    assert looked_up.json() == details


def test_node_details_for_member_and_type(client, pid):
    nodes = structure(client, pid)["nodes"]
    member = next(n for n in nodes if n["node_type"] == "member" and n["kind"] == "method")
    type_node = next(n for n in nodes if n["node_type"] == "type")
    for node in (member, type_node):
        response = client.post(f"/api/projects/{pid}/nodes/lookup", json={"node_id": node["id"]})
        assert response.status_code == 200, (node["id"], response.text)
        assert response.json()["node_id"] == node["id"]
    assert (
        client.post(
            f"/api/projects/{pid}/nodes/lookup", json={"node_id": "Nope.java#X"}
        ).status_code
        == 404
    )


def test_locate_finds_innermost_block_and_is_stable_for_blank_lines(client, pid):
    method_id, node = first_flow_node(client, pid)
    span = node["range"]
    response = client.get(
        f"/api/projects/{pid}/locate",
        params={"file": span["file"], "line": span["start_line"], "column": span["start_col"]},
    )
    assert response.status_code == 200
    found = response.json()
    assert found["method_id"] == method_id
    assert found["node_id"].startswith(method_id)


def test_locate_outside_any_declaration_is_empty(client, make_project):
    project = make_project({"A.java": "// комментарий\n\nclass A {}\n"})
    response = client.get(
        f"/api/projects/{project['id']}/locate", params={"file": "A.java", "line": 1, "column": 1}
    )
    assert response.json() == {"node_id": None, "method_id": None}


def test_locate_validates_arguments(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}/locate"
    assert client.get(url, params={"file": "Main.java", "line": 0, "column": 1}).status_code == 400
    assert client.get(url, params={"file": "Nope.java", "line": 1, "column": 1}).status_code == 404


def test_graphs_follow_the_requested_version(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}"
    changed = client.post(
        f"{url}/files", json={"path": "Extra.java", "content": "class Extra { void f() {} }"}
    ).json()

    old = client.get(
        f"{url}/structure", params={"version_id": project["original_version_id"]}
    ).json()
    new = client.get(f"{url}/structure").json()
    assert new["version_id"] == changed["version"]["id"]
    assert old["content_hash"] != new["content_hash"]
    assert len(new["nodes"]) > len(old["nodes"])


def test_graph_endpoints_survive_broken_code(client, make_project):
    project = make_project({"Broken.java": "class Broken { void m() { int x = 1 foo(); } }"})
    url = f"/api/projects/{project['id']}"
    assert client.get(f"{url}/structure").status_code == 200
    assert client.get(f"{url}/tree").status_code == 200
    flow = client.get(f"{url}/flow", params={"method_id": "Broken.java#Broken.m()"})
    assert flow.status_code == 200
    assert flow.json()["nodes"]


def test_openapi_is_served_with_graph_routes():
    schema = create_app().openapi()
    assert "/api/projects/{project_id}/structure" in schema["paths"]
