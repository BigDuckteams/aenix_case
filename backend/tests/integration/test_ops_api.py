"""Операции над графом через API (S5.7–S5.8): версия `graph_op`, атомарность, ошибки, палитра."""

from __future__ import annotations

import pytest

CODE = """\
import java.util.*;

public class Main {
    public static void main(String[] args) {
        int sum = 0;
        for (int i = 0; i < 3; i++) {
            sum += i;
        }
        System.out.println(sum);
    }
}
"""
MAIN = "Main.java#Main.main(String[])"


@pytest.fixture
def project(make_project):
    return make_project({"Main.java": CODE}, name="ops")


def url(project, suffix: str) -> str:
    return f"/api/projects/{project['id']}{suffix}"


def post_ops(client, project, ops, base=None, **extra):
    body = {"base_version_id": base or project["head_version_id"], "ops": ops, **extra}
    return client.post(url(project, "/ops"), json=body)


def insert(index=1, expr="log()", parent=MAIN, slot="body") -> dict:
    return {
        "op": "insert_node",
        "parent_id": parent,
        "slot": slot,
        "index": index,
        "kind": "operation",
        "fields": {"expr": expr},
    }


def content(client, project, version=None) -> str:
    params = {"version_id": version} if version else {}
    return client.get(url(project, "/files/Main.java"), params=params).json()["content"]


def test_apply_creates_a_graph_op_version_with_focus_flow_and_id_map(client, project):
    response = post_ops(client, project, [insert(0, "log()")])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"]["origin"] == "graph_op"
    assert body["version"]["parent_id"] == project["head_version_id"]
    assert body["version"]["description"] == "Граф: insert_node"
    assert body["changed_files"] == ["Main.java"]
    assert body["focus_node_id"] == f"{MAIN}/op[0]"
    assert body["id_map"][f"{MAIN}/op[0]"] == f"{MAIN}/op[1]"
    assert body["syntax_errors"] == []
    flow = body["flow"]
    assert flow["method_id"] == MAIN and flow["version_id"] == body["version"]["id"]
    assert any(n["id"] == f"{MAIN}/op[0]" and n["code"] == "log();" for n in flow["nodes"])
    assert "        log();\n        int sum = 0;" in content(client, project)


def test_batch_is_atomic_and_ids_refer_to_the_state_after_previous_ops(client, project):
    ops = [
        insert(0, "first()"),
        {"op": "update_node", "node_id": f"{MAIN}/op[0]", "fields": {"expr": "renamed()"}},
    ]
    response = post_ops(client, project, ops, description="две правки")
    assert response.status_code == 200, response.text
    assert response.json()["version"]["description"] == "две правки"
    assert "renamed();" in content(client, project) and "first();" not in content(client, project)

    versions_before = len(client.get(url(project, "/versions")).json()["versions"])
    head = client.get(url(project, "/versions")).json()["head_version_id"]
    failing = post_ops(client, project, [insert(0, "ok()"), insert(0, "broken(")], base=head)
    assert failing.status_code == 422
    assert len(client.get(url(project, "/versions")).json()["versions"]) == versions_before
    assert "ok();" not in content(client, project)


def test_error_format_for_invalid_fragment_precondition_and_not_found(client, project):
    bad = post_ops(client, project, [insert(0, "1 +")])
    assert bad.status_code == 422
    error = bad.json()["error"]
    assert error["code"] == "INVALID_FRAGMENT"
    assert error["details"] == {"op_index": 0, "field": "expr"}

    second = post_ops(
        client, project, [insert(0, "ok()"), {"op": "duplicate_node", "node_id": f"{MAIN}/var[0]"}]
    )
    assert second.status_code == 422
    assert second.json()["error"]["code"] == "PRECONDITION_FAILED"
    assert second.json()["error"]["details"]["op_index"] == 1

    missing = post_ops(client, project, [{"op": "delete_node", "node_id": f"{MAIN}/for[7]"}])
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    unsupported = post_ops(
        client, project, [{"op": "update_node", "node_id": MAIN, "fields": {"expr": "x"}}]
    )
    assert unsupported.status_code == 422 and unsupported.json()["error"]["code"] == "UNSUPPORTED"

    assert post_ops(client, project, [{"op": "explode", "node_id": "x"}]).status_code == 400


def test_stale_base_version_is_409(client, project):
    stale = project["head_version_id"]
    assert post_ops(client, project, [insert(0, "a()")]).status_code == 200
    response = post_ops(client, project, [insert(0, "b()")], base=stale)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_undo_returns_the_text_before_the_operation(client, project):
    post_ops(client, project, [insert(0, "a()")])
    assert "a();" in content(client, project)
    client.post(url(project, "/undo"))
    assert content(client, project) == CODE
    client.post(url(project, "/redo"))
    assert "a();" in content(client, project)


def test_ops_that_change_nothing_do_not_create_versions(client, project):
    response = post_ops(
        client,
        project,
        [{"op": "replace_code", "node_id": f"{MAIN}/var[0]", "text": "int sum = 0;"}],
    )
    assert response.status_code == 200
    assert response.json()["version"]["id"] == project["head_version_id"]
    assert response.json()["changed_files"] == []
    assert len(client.get(url(project, "/versions")).json()["versions"]) == 1


def test_validate_previews_the_diff_without_saving(client, project):
    ok = client.post(
        url(project, "/ops/validate"),
        json={"base_version_id": project["head_version_id"], "ops": [insert(0, "log()")]},
    ).json()
    assert ok["ok"] is True and ok["errors"] == []
    [diff] = ok["diff"]
    assert diff["path"] == "Main.java" and diff["status"] == "modified"
    assert "+        log();" in diff["unified"]
    assert len(client.get(url(project, "/versions")).json()["versions"]) == 1

    bad = client.post(
        url(project, "/ops/validate"),
        json={"base_version_id": project["head_version_id"], "ops": [insert(0, "x +")]},
    ).json()
    assert bad["ok"] is False and bad["diff"] == []
    assert (bad["errors"][0]["code"], bad["errors"][0]["field"], bad["errors"][0]["op_index"]) == (
        "INVALID_FRAGMENT",
        "expr",
        0,
    )


def test_palette_matches_the_templates(client, project):
    palette = client.get(url(project, "/palette")).json()
    kinds = [b["kind"] for b in palette["blocks"]]
    assert {
        "var_decl",
        "assign",
        "operation",
        "condition",
        "loop_for",
        "loop_foreach",
        "loop_while",
        "try",
        "return",
    } <= set(kinds)
    samples = {"expression": "x", "type": "int", "identifier": "v", "text": "x", "boolean": False}
    for block in palette["blocks"]:
        fields = {}
        for field in block["fields"]:
            if field["type"] == "select":
                fields[field["name"]] = field["options"][0]
            elif block["kind"] == "loop_for" and field["name"] in {"init", "update"}:
                fields[field["name"]] = "i = 0" if field["name"] == "init" else "i++"
            elif block["kind"] == "assign" and field["name"] == "target":
                fields["target"] = "sum"
            else:
                fields[field["name"]] = samples[field["type"]]
        if block["kind"] == "code":
            fields["text"] = "int raw = 1;"
        if block["kind"] == "assign":
            fields["op"] = "="
            fields["value"] = "1"
        result = client.post(
            url(project, "/ops/validate"),
            json={
                "base_version_id": project["head_version_id"],
                "ops": [
                    {
                        "op": "insert_node",
                        "parent_id": MAIN,
                        "slot": "body",
                        "index": 0,
                        "kind": block["kind"],
                        "fields": fields,
                    }
                ],
            },
        ).json()
        assert result["ok"], (block["kind"], result["errors"])
    assert all(b["template"] and b["icon"] and b["color"] for b in palette["blocks"])


def test_validate_expression(client, project):
    def check(**body):
        return client.post(url(project, "/validate/expression"), json=body).json()

    assert check(kind="expression", text="a + b * 2")["ok"] is True
    assert check(kind="type", text="List<String>")["ok"] is True
    assert check(kind="identifier", text="total")["ok"] is True
    broken = check(kind="expression", text="a +")
    assert broken["ok"] is False and broken["error"]["message"]
    assert check(kind="type", text="int int")["ok"] is False
    assert check(kind="identifier", text="9x")["ok"] is False
    taken = check(kind="identifier", text="sum", context_node_id=MAIN)
    assert taken["ok"] is False and "занято" in taken["error"]["message"]
    assert check(kind="identifier", text="fresh", context_node_id=MAIN)["ok"] is True
    assert (
        client.post(
            url(project, "/validate/expression"), json={"kind": "other", "text": "x"}
        ).status_code
        == 400
    )


def test_rename_and_member_operations_through_the_api(client, make_project):
    files = {
        "Shop.java": "public class Shop {\n    int price(int base) {\n        return base * 2;\n    }\n\n    int total() {\n        return price(1) + price(2);\n    }\n}\n"
    }
    shop = make_project(files, name="shop")
    response = client.post(
        url(shop, "/ops"),
        json={
            "base_version_id": shop["head_version_id"],
            "ops": [
                {
                    "op": "rename_symbol",
                    "symbol_id": "Shop.java#Shop.price(int)",
                    "new_name": "cost",
                },
                {
                    "op": "add_member",
                    "type_id": "Shop.java#Shop",
                    "kind": "field",
                    "fields": {"type": "int", "name": "rate", "value": "3"},
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    text = client.get(url(shop, "/files/Shop.java")).json()["content"]
    assert "int cost(int base)" in text and "cost(1) + cost(2)" in text and "price" not in text
    assert "private int rate = 3;" in text


@pytest.mark.jdk
def test_edited_demo_orders_still_compiles(client, demo_orders):
    pid = demo_orders["id"]
    structure = client.get(f"/api/projects/{pid}/structure").json()
    method = next(
        n["id"]
        for n in structure["nodes"]
        if n["node_type"] == "member" and n["kind"] == "method" and n["name"] == "mergeDuplicates"
    )
    flow = client.get(f"/api/projects/{pid}/flow", params={"method_id": method}).json()
    loop = next(n["id"] for n in flow["nodes"] if n["kind"] == "loop_foreach")
    ops = [
        {
            "op": "insert_node",
            "parent_id": method,
            "slot": "body",
            "index": 0,
            "kind": "operation",
            "fields": {"expr": 'System.err.println("start")'},
        },
        {"op": "wrap_node", "node_ids": [loop.replace(method, method)], "wrapper": "block"},
        {
            "op": "rename_symbol",
            "symbol_id": "Main.java#Main.mergeDuplicates()",
            "new_name": "mergeAll",
        },
    ]
    response = client.post(
        f"/api/projects/{pid}/ops",
        json={"base_version_id": demo_orders["head_version_id"], "ops": ops},
    )
    assert response.status_code == 200, response.text
    build = client.post(f"/api/projects/{pid}/build", json={}).json()
    assert build["ok"], build["diagnostics"]
