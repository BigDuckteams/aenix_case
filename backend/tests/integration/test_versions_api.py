"""Версии и файлы (S3.3, docs/08-api.md § 3): схлопывание правок, конфликты, undo/redo, diff."""

from __future__ import annotations

from tests.integration.conftest import HELLO

SOURCE = HELLO["Main.java"]
EDITED = SOURCE.replace('"hi"', '"hello"')
EDITED_AGAIN = SOURCE.replace('"hi"', '"hey"')


def save(client, project, path, content, base):
    return client.put(
        f"/api/projects/{project['id']}/files/{path}",
        json={"base_version_id": base, "content": content},
    )


def versions(client, project) -> list[dict]:
    return client.get(f"/api/projects/{project['id']}/versions").json()["versions"]


def head(client, project) -> int:
    return client.get(f"/api/projects/{project['id']}/versions").json()["head_version_id"]


def error_code(response) -> str:
    return response.json()["error"]["code"]


# --- сохранение и схлопывание -------------------------------------------------------------------


def test_save_creates_code_edit_version_and_moves_head(client, make_project):
    project = make_project()
    response = save(client, project, "Main.java", EDITED, project["head_version_id"])
    assert response.status_code == 200, response.text
    change = response.json()
    assert change["version"]["origin"] == "code_edit"
    assert change["version"]["parent_id"] == project["head_version_id"]
    assert change["collapsed"] is False
    assert change["changed_files"] == ["Main.java"]
    assert change["head_version_id"] == change["version"]["id"] == head(client, project)

    stored = client.get(f"/api/projects/{project['id']}/files/Main.java").json()
    assert stored["content"] == EDITED
    original = client.get(
        f"/api/projects/{project['id']}/files/Main.java",
        params={"version_id": project["original_version_id"]},
    ).json()
    assert original["content"] == SOURCE


def test_consecutive_edits_collapse_into_head(client, make_project):
    project = make_project()
    first = save(client, project, "Main.java", EDITED, project["head_version_id"]).json()
    second = save(client, project, "Main.java", EDITED_AGAIN, first["version"]["id"]).json()

    assert second["collapsed"] is True
    assert second["version"]["id"] == first["version"]["id"]
    assert len(versions(client, project)) == 2
    content = client.get(f"/api/projects/{project['id']}/files/Main.java").json()["content"]
    assert content == EDITED_AGAIN
    # хеш версии обновился вместе с содержимым
    assert second["version"]["content_hash"] != first["version"]["content_hash"]


def test_same_content_does_not_create_a_version(client, make_project):
    project = make_project()
    change = save(client, project, "Main.java", SOURCE, project["head_version_id"]).json()
    assert change["version"]["id"] == project["head_version_id"]
    assert change["changed_files"] == []
    assert len(versions(client, project)) == 1


def test_edit_after_non_edit_head_does_not_collapse_into_the_original(client, make_project):
    project = make_project()
    change = save(client, project, "Main.java", EDITED, project["head_version_id"]).json()
    assert change["version"]["id"] != project["original_version_id"]
    assert len(versions(client, project)) == 2


def test_stale_base_version_is_409(client, make_project):
    project = make_project()
    save(client, project, "Main.java", EDITED, project["head_version_id"])
    stale = save(client, project, "Main.java", EDITED_AGAIN, project["head_version_id"])
    assert stale.status_code == 409
    assert error_code(stale) == "VERSION_CONFLICT"
    assert stale.json()["error"]["details"]["head_version_id"] == head(client, project)


def test_saving_unknown_file_is_404_and_syntax_errors_are_reported(client, make_project):
    project = make_project()
    missing = save(client, project, "Nope.java", "class N {}", project["head_version_id"])
    assert missing.status_code == 404

    broken = save(
        client, project, "Main.java", "class Main { void m() { int x = ; } }", head(client, project)
    ).json()
    assert broken["syntax_errors"]
    assert broken["syntax_errors"][0]["range"]["file"] == "Main.java"


def test_file_over_2_mb_is_413_and_path_traversal_is_400(client, make_project):
    project = make_project()
    huge = "class Main {}\n// " + "x" * (2 * 1024 * 1024)
    assert save(client, project, "Main.java", huge, project["head_version_id"]).status_code == 413
    assert client.get(f"/api/projects/{project['id']}/files/..%2F..%2Fetc").status_code in {
        400,
        404,
    }


# --- файлы ------------------------------------------------------------------------------------------


def test_create_and_delete_file_make_versions(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}"

    created = client.post(
        f"{url}/files",
        json={"path": "util/Helper.java", "content": "package util; class Helper {}"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["changed_files"] == ["util/Helper.java"]
    listing = client.get(f"{url}/files").json()
    assert [f["path"] for f in listing["files"]] == ["Main.java", "util/Helper.java"]

    deleted = client.delete(f"{url}/files/util/Helper.java")
    assert deleted.status_code == 200
    assert deleted.json()["changed_files"] == ["util/Helper.java"]
    assert [f["path"] for f in client.get(f"{url}/files").json()["files"]] == ["Main.java"]
    assert len(versions(client, project)) == 3


def test_file_creation_and_deletion_errors(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}"
    assert client.post(f"{url}/files", json={"path": "Main.java"}).status_code == 400  # уже есть
    assert client.post(f"{url}/files", json={"path": "notes.txt"}).status_code == 400
    assert client.post(f"{url}/files", json={"path": "../A.java"}).status_code == 400
    assert client.delete(f"{url}/files/Nope.java").status_code == 404
    assert client.delete(f"{url}/files/Main.java").status_code == 400  # последний файл
    assert client.get(f"{url}/files/Nope.java").status_code == 404


def test_version_detail_and_unknown_version(client, make_project):
    project = make_project()
    detail = client.get(
        f"/api/projects/{project['id']}/versions/{project['head_version_id']}"
    ).json()
    assert detail["version"]["number"] == 1
    assert [f["path"] for f in detail["files"]] == ["Main.java"]
    assert detail["files"][0]["lines"] == 5
    assert client.get(f"/api/projects/{project['id']}/versions/9999").status_code == 404
    other = make_project(name="other")
    # версия чужого проекта недоступна через этот проект
    assert (
        client.get(f"/api/projects/{project['id']}/versions/{other['head_version_id']}").status_code
        == 404
    )


# --- undo / redo / restore ---------------------------------------------------------------------------


def test_undo_and_redo_move_head_along_the_chain(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}"
    edited = save(client, project, "Main.java", EDITED, project["head_version_id"]).json()

    undone = client.post(f"{url}/undo")
    assert undone.status_code == 200
    assert undone.json()["head_version_id"] == project["head_version_id"]
    assert undone.json()["changed_files"] == ["Main.java"]
    assert client.get(f"{url}/files/Main.java").json()["content"] == SOURCE

    redone = client.post(f"{url}/redo")
    assert redone.status_code == 200
    assert redone.json()["head_version_id"] == edited["version"]["id"]
    assert client.get(f"{url}/files/Main.java").json()["content"] == EDITED


def test_undo_at_the_first_version_and_redo_at_the_tip_are_400(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}"
    assert client.post(f"{url}/undo").status_code == 400
    assert client.post(f"{url}/redo").status_code == 400


def test_editing_after_undo_starts_a_branch(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}"
    save(client, project, "Main.java", EDITED, project["head_version_id"])
    client.post(f"{url}/undo")

    branch = save(client, project, "Main.java", EDITED_AGAIN, head(client, project)).json()
    assert branch["version"]["parent_id"] == project["head_version_id"]
    assert branch["collapsed"] is False
    assert len(versions(client, project)) == 3
    # редо не перепрыгивает на старую ветку: у новой вершины нет потомков
    assert client.post(f"{url}/redo").status_code == 400


def test_restore_creates_a_revert_version_with_the_old_files(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}"
    save(client, project, "Main.java", EDITED, project["head_version_id"])

    restored = client.post(f"{url}/versions/{project['original_version_id']}/restore")
    assert restored.status_code == 200, restored.text
    change = restored.json()
    assert change["version"]["origin"] == "revert"
    assert change["version"]["number"] == 3
    assert client.get(f"{url}/files/Main.java").json()["content"] == SOURCE
    assert head(client, project) == change["version"]["id"]


# --- diff -------------------------------------------------------------------------------------------


def test_diff_lists_changed_files_with_unified_text(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}"
    client.post(f"{url}/files", json={"path": "Extra.java", "content": "class Extra {}"})
    new_head = save(client, project, "Main.java", EDITED, head(client, project)).json()

    diff = client.get(
        f"{url}/diff",
        params={"from": project["original_version_id"], "to": new_head["version"]["id"]},
    ).json()
    by_path = {f["path"]: f for f in diff["files"]}
    assert by_path["Extra.java"]["status"] == "added"
    assert by_path["Main.java"]["status"] == "modified"
    assert '-        System.out.println("hi");' in by_path["Main.java"]["unified"]
    assert by_path["Main.java"]["before"] == SOURCE
    assert by_path["Main.java"]["after"] == EDITED

    assert client.get(f"{url}/diff", params={"from": 1, "to": 999}).status_code == 404
    same = client.get(f"{url}/diff", params={"from": 1, "to": 1}).json()
    assert same["files"] == []


# --- живой разбор -----------------------------------------------------------------------------------------


def test_live_parse_returns_flow_and_syntax_errors_without_saving(client, make_project):
    project = make_project()
    url = f"/api/projects/{project['id']}"

    ok = client.post(
        f"{url}/parse",
        json={"file": "Main.java", "content": EDITED, "method_key": "main(String[])"},
    ).json()
    assert ok["syntax_errors"] == []
    assert ok["flow"]["method_id"] == "Main.java#Main.main(String[])"
    assert len(versions(client, project)) == 1  # ничего не сохранено
    assert client.get(f"{url}/files/Main.java").json()["content"] == SOURCE

    broken = client.post(
        f"{url}/parse", json={"file": "Main.java", "content": "class Main { int x = ; }"}
    ).json()
    assert broken["syntax_errors"]
    assert broken["flow"] is None
