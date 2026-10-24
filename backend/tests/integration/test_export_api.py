"""Экспорт исходников (S3.3): zip с ``src/…`` воспроизводим и собирается ``javac``."""

from __future__ import annotations

import io
import subprocess
import zipfile

import pytest

from app.config import get_settings
from engine.runtime.jdk import tool_path
from tests.integration.conftest import HELLO


def export(client, project, **params):
    return client.get(f"/api/projects/{project['id']}/export/source", params=params)


def test_zip_contains_src_tree_in_utf8(client, make_project):
    files = {
        **HELLO,
        "util/Приветствие.java": 'package util; public class Hello { String s = "привет"; }',
    }
    project = make_project(files)
    response = export(client, project)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    assert f"project-{project['id']}-v1.zip" in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["src/Main.java", "src/util/Приветствие.java"]
        assert archive.read("src/Main.java").decode("utf-8") == HELLO["Main.java"]
        assert "привет" in archive.read("src/util/Приветствие.java").decode("utf-8")


def test_zip_is_byte_for_byte_reproducible(client, make_project):
    project = make_project()
    assert export(client, project).content == export(client, project).content


def test_zip_follows_the_requested_version(client, make_project):
    project = make_project()
    edited = HELLO["Main.java"].replace('"hi"', '"edited"')
    client.put(
        f"/api/projects/{project['id']}/files/Main.java",
        json={"base_version_id": project["head_version_id"], "content": edited},
    )

    def main_of(response) -> str:
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            return archive.read("src/Main.java").decode("utf-8")

    assert main_of(export(client, project)) == edited
    assert (
        main_of(export(client, project, version_id=project["original_version_id"]))
        == HELLO["Main.java"]
    )
    assert export(client, project, version_id=999).status_code == 404


def test_single_file_export(client, make_project):
    project = make_project()
    response = export(client, project, format="file", path="Main.java")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/x-java-source")
    assert 'filename="Main.java"' in response.headers["content-disposition"]
    assert response.content.decode("utf-8") == HELLO["Main.java"]

    assert export(client, project, format="file").status_code == 400
    assert export(client, project, format="file", path="Nope.java").status_code == 404
    assert export(client, project, format="file", path="../Main.java").status_code == 400


@pytest.mark.jdk
def test_exported_zip_compiles_with_javac(client, make_project, tmp_path):
    project = make_project(
        {
            "Main.java": "import util.Greeter;\npublic class Main { public static void main(String[] a) { System.out.println(new Greeter().hi()); } }",
            "util/Greeter.java": 'package util; public class Greeter { public String hi() { return "привет"; } }',
        }
    )
    with zipfile.ZipFile(io.BytesIO(export(client, project).content)) as archive:
        archive.extractall(tmp_path)
    javac = tool_path("javac", get_settings().java_home)
    assert javac is not None
    sources = [str(p) for p in (tmp_path / "src").rglob("*.java")]
    done = subprocess.run(
        [javac, "-encoding", "UTF-8", "-d", str(tmp_path / "out"), *sources],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
