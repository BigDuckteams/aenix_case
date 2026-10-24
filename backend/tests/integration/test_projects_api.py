"""Проекты и импорт (S3.1–S3.2, docs/08-api.md § 2): форматы тела, лимиты, защита путей."""

from __future__ import annotations

import io
import zipfile

from sqlmodel import Session, select

from app.db.models import Scenario, SourceFile, Version
from tests.integration.conftest import HELLO

BROKEN = "public class Broken { void m() { int x = ; } }"


def error_code(response) -> str:
    return response.json()["error"]["code"]


def zip_of(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


# --- создание ------------------------------------------------------------------------------------


def test_create_from_json_returns_main_class_files_and_first_version(client, make_project):
    created = make_project()
    assert created["name"] == "demo"
    assert created["main_class"] == "Main"
    assert created["main_class_candidates"] == ["Main"]
    assert created["head_version_id"] == created["original_version_id"]
    assert [f["path"] for f in created["files"]] == ["Main.java"]
    assert created["syntax_errors"] == []

    versions = client.get(f"/api/projects/{created['id']}/versions").json()
    assert versions["head_version_id"] == created["head_version_id"]
    [only] = versions["versions"]
    assert (only["number"], only["origin"], only["description"]) == (1, "upload", "Оригинал")
    assert only["parent_id"] is None


def test_create_from_multipart_files(client):
    response = client.post(
        "/api/projects",
        data={"name": "multi"},
        files=[
            ("files", ("Main.java", HELLO["Main.java"].encode(), "text/x-java")),
            ("files", ("util/Helper.java", b"package util; public class Helper {}", "text/x-java")),
        ],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "multi"
    assert [f["path"] for f in body["files"]] == ["Main.java", "util/Helper.java"]


def test_create_from_zip_keeps_only_java_and_names_project_after_archive(client):
    archive = zip_of(
        {
            "src/Main.java": HELLO["Main.java"].encode(),
            "README.md": b"# readme",
            "__MACOSX/src/._Main.java": b"junk",
            "build/": b"",
        }
    )
    response = client.post(
        "/api/projects", files={"archive": ("shop.zip", archive, "application/zip")}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "shop"
    assert [f["path"] for f in body["files"]] == ["src/Main.java"]


def test_zip_slip_is_rejected(client):
    archive = zip_of({"../evil/Main.java": b"class Main {}"})
    response = client.post(
        "/api/projects", files={"archive": ("x.zip", archive, "application/zip")}
    )
    assert response.status_code == 400
    assert error_code(response) == "BAD_REQUEST"


def test_broken_zip_is_rejected(client):
    response = client.post(
        "/api/projects", files={"archive": ("x.zip", b"not a zip", "application/zip")}
    )
    assert response.status_code == 400


def test_unsafe_paths_are_rejected(client):
    for path in ("../Main.java", "/etc/Main.java", "C:/Main.java", "a/../../Main.java", ""):
        response = client.post(
            "/api/projects",
            json={"name": "x", "files": [{"path": path, "content": "class A {}"}]},
        )
        assert response.status_code == 400, path


def test_backslash_paths_are_normalised(client):
    response = client.post(
        "/api/projects",
        json={
            "name": "x",
            "files": [{"path": "pkg\\A.java", "content": "package pkg; class A {}"}],
        },
    )
    assert response.status_code == 201
    assert response.json()["files"][0]["path"] == "pkg/A.java"


def test_only_java_files_are_accepted(client):
    response = client.post(
        "/api/projects", json={"name": "x", "files": [{"path": "notes.txt", "content": "hello"}]}
    )
    assert response.status_code == 400


def test_duplicate_paths_are_rejected(client):
    response = client.post(
        "/api/projects",
        json={
            "name": "x",
            "files": [
                {"path": "A.java", "content": "class A {}"},
                {"path": "./A.java", "content": "class A {}"},
            ],
        },
    )
    assert response.status_code == 400


def test_non_utf8_file_is_rejected(client):
    response = client.post(
        "/api/projects",
        files=[
            ("files", ("A.java", "class Ä {}".encode("cp1251", errors="replace") + b"\xff", ""))
        ],
    )
    assert response.status_code == 400
    assert "UTF-8" in response.json()["error"]["message"]


def test_utf8_bom_is_stripped(client):
    response = client.post(
        "/api/projects",
        files=[("files", ("A.java", b"\xef\xbb\xbfclass A {}", "text/x-java"))],
    )
    assert response.status_code == 201
    project_id = response.json()["id"]
    content = client.get(f"/api/projects/{project_id}/files/A.java").json()["content"]
    assert content == "class A {}"


def test_file_over_2_mb_is_413(client):
    big = "class A {}\n" + "// " + "x" * (2 * 1024 * 1024)
    response = client.post(
        "/api/projects", json={"name": "x", "files": [{"path": "A.java", "content": big}]}
    )
    assert response.status_code == 413
    assert error_code(response) == "PAYLOAD_TOO_LARGE"


def test_archive_over_10_mb_is_413(client):
    blob = b"\0" * (10 * 1024 * 1024 + 1)
    response = client.post("/api/projects", files={"archive": ("x.zip", blob, "application/zip")})
    assert response.status_code == 413


def test_more_than_200_files_is_413(client):
    files = [{"path": f"p/A{i}.java", "content": f"class A{i} {{}}"} for i in range(201)]
    response = client.post("/api/projects", json={"name": "x", "files": files})
    assert response.status_code == 413


def test_empty_project_and_blank_name_are_rejected(client):
    assert client.post("/api/projects", json={"name": "x", "files": []}).status_code == 400
    blank = client.post(
        "/api/projects", json={"name": "  ", "files": [{"path": "A.java", "content": ""}]}
    )
    assert blank.status_code == 400


def test_non_json_body_is_rejected(client):
    response = client.post(
        "/api/projects", content=b"{oops", headers={"content-type": "application/json"}
    )
    assert response.status_code == 400
    assert error_code(response) == "BAD_REQUEST"


def test_syntax_errors_are_reported_but_project_is_created(client, make_project):
    created = make_project({"Broken.java": BROKEN})
    [issue] = created["syntax_errors"][:1]
    assert issue["range"]["file"] == "Broken.java"
    assert issue["range"]["start_line"] == 1


def test_several_mains_are_all_candidates_and_first_is_chosen(client, make_project):
    main = "public class {n} {{ public static void main(String[] a) {{}} }}"
    created = make_project({"A.java": main.format(n="A"), "B.java": main.format(n="B")})
    assert created["main_class"] == "A"
    assert created["main_class_candidates"] == ["A", "B"]


def test_project_without_main_has_no_main_class(make_project):
    created = make_project({"A.java": "class A {}"})
    assert created["main_class"] is None
    assert created["main_class_candidates"] == []


# --- примеры -------------------------------------------------------------------------------------


def test_samples_list_contains_demo_orders(client):
    samples = {s["id"]: s for s in client.get("/api/samples").json()["samples"]}
    assert "demo-orders" in samples
    assert samples["demo-orders"]["lines"] > 500


def test_sample_import_creates_scenarios(client, session: Session):
    response = client.post("/api/projects", json={"sample_id": "demo-orders", "name": "Магазин"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Магазин"
    assert body["main_class"] == "Main"
    names = {s.name for s in session.exec(select(Scenario)).all()}
    assert len(names) == 11


def test_unknown_sample_is_404(client):
    response = client.post("/api/projects", json={"sample_id": "nope"})
    assert response.status_code == 404
    assert error_code(response) == "NOT_FOUND"


# --- чтение, изменение, удаление ----------------------------------------------------------------


def test_list_and_get_project(client, make_project):
    assert client.get("/api/projects").json() == {"projects": []}
    created = make_project(name="one")
    make_project(name="two")

    listed = client.get("/api/projects").json()["projects"]
    assert [p["name"] for p in listed] == ["one", "two"]
    assert listed[0]["files_count"] == 1

    detail = client.get(f"/api/projects/{created['id']}").json()
    assert detail["main_class"] == "Main"
    assert detail["settings"]["run_timeout_s"] >= 1
    assert detail["gate"]["status"] == "unknown"
    assert detail["baseline_version_id"] == created["original_version_id"]


def test_unknown_project_is_404(client):
    response = client.get("/api/projects/999")
    assert response.status_code == 404
    assert error_code(response) == "NOT_FOUND"


def test_patch_name_main_class_and_settings(client, make_project):
    main = "public class {n} {{ public static void main(String[] a) {{}} }}"
    created = make_project({"A.java": main.format(n="A"), "B.java": main.format(n="B")})
    url = f"/api/projects/{created['id']}"

    patched = client.patch(
        url,
        json={"name": " Новое имя ", "main_class": "B", "settings": {"run_timeout_s": 3}},
    ).json()
    assert patched["name"] == "Новое имя"
    assert patched["main_class"] == "B"
    assert patched["settings"]["run_timeout_s"] == 3
    assert patched["settings"]["compile_timeout_s"] >= 1  # остальное сохранено

    again = client.patch(url, json={"settings": {"locale": "ru_RU"}}).json()
    assert again["settings"]["run_timeout_s"] == 3
    assert again["settings"]["locale"] == "ru_RU"


def test_patch_rejects_non_main_class_and_blank_name(client, make_project):
    created = make_project()
    url = f"/api/projects/{created['id']}"
    bad = client.patch(url, json={"main_class": "Nope"})
    assert bad.status_code == 400
    assert bad.json()["error"]["details"]["main_class_candidates"] == ["Main"]
    assert client.patch(url, json={"name": " "}).status_code == 400
    assert client.patch(url, json={"settings": {"run_timeout_s": 0}}).status_code == 400


def test_delete_project_removes_versions_and_files(client, make_project, session: Session):
    keep = make_project(name="keep")
    gone = make_project({"A.java": "class A {}"}, name="gone")
    client.put(
        f"/api/projects/{gone['id']}/files/A.java",
        json={"base_version_id": gone["head_version_id"], "content": "class A { int x; }"},
    )

    response = client.delete(f"/api/projects/{gone['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/projects/{gone['id']}").status_code == 404

    session.expire_all()
    assert {v.project_id for v in session.exec(select(Version)).all()} == {keep["id"]}
    assert len(session.exec(select(SourceFile)).all()) == 1
    assert client.get(f"/api/projects/{keep['id']}").status_code == 200
