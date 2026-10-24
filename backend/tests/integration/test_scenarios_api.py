"""Сценарии (S6.1, docs/08 § 8.1): CRUD, импорт/экспорт, сброс эталона, ожидания организаторов."""

from __future__ import annotations

from sqlmodel import Session, select

from app.db.models import Baseline


def url(project, suffix: str = "") -> str:
    return f"/api/projects/{project['id']}/scenarios{suffix}"


def create(client, project, name="one", **body):
    response = client.post(url(project), json={"name": name, **body})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_list_update_delete(client, make_project):
    project = make_project()
    created = create(client, project, "пустой ввод", description="ничего", stdin="", args=["-v"])
    assert created["source"] == "manual"
    assert created["enabled"] is True
    assert created["stability"] == "stable"
    assert created["baseline"] == {"state": "none", "version_id": None, "duration_ms": None}

    second = create(client, project, "два числа", stdin="1 2\n")
    listed = client.get(url(project)).json()["scenarios"]
    assert [s["id"] for s in listed] == [created["id"], second["id"]]

    updated = client.put(
        url(project, f"/{created['id']}"),
        json={"name": "пусто", "description": "-", "enabled": False},
    ).json()
    assert (updated["name"], updated["enabled"], updated["args"]) == ("пусто", False, ["-v"])

    assert client.delete(url(project, f"/{second['id']}")).status_code == 204
    assert [s["name"] for s in client.get(url(project)).json()["scenarios"]] == ["пусто"]
    assert client.delete(url(project, f"/{second['id']}")).status_code == 404


def test_validation_of_names_masks_and_input(client, make_project):
    project = make_project()
    create(client, project, "a")
    assert client.post(url(project), json={"name": "a"}).status_code == 400  # дубль
    assert client.post(url(project), json={"name": "  "}).status_code == 400
    assert (
        client.post(
            url(project), json={"name": "big", "stdin": "x" * (2 * 1024 * 1024 + 1)}
        ).status_code
        == 400
    )
    assert client.post(url(project), json={"name": "nul", "args": ["a\u0000b"]}).status_code == 400

    other = create(client, project, "b")
    clash = client.put(url(project, f"/{other['id']}"), json={"name": "a"})
    assert clash.status_code == 400
    bad_mask = client.put(
        url(project, f"/{other['id']}"), json={"masks": [{"pattern": "(", "replacement": "x"}]}
    )
    assert bad_mask.status_code == 400
    assert client.put(url(project, "/999"), json={"name": "z"}).status_code == 404


def test_scenarios_are_scoped_to_their_project(client, make_project):
    mine, theirs = make_project(name="a"), make_project(name="b")
    foreign = create(client, theirs, "чужой")
    assert client.put(url(mine, f"/{foreign['id']}"), json={"name": "x"}).status_code == 404
    assert client.delete(url(mine, f"/{foreign['id']}")).status_code == 404
    assert client.get(url(mine)).json() == {"scenarios": []}


def test_changing_input_resets_the_baseline_but_renaming_does_not(
    client, make_project, session: Session
):
    project = make_project()
    scenario = create(client, project, "s", stdin="1\n")
    session.add(
        Baseline(
            project_id=project["id"],
            scenario_id=scenario["id"],
            version_id=project["original_version_id"],
            stdout="out",
            duration_ms=7,
        )
    )
    session.commit()

    state = lambda: client.get(url(project)).json()["scenarios"][0]["baseline"]  # noqa: E731
    assert state() == {
        "state": "recorded",
        "version_id": project["original_version_id"],
        "duration_ms": 7,
    }

    client.put(url(project, f"/{scenario['id']}"), json={"name": "renamed", "enabled": False})
    assert state()["state"] == "recorded"

    client.put(url(project, f"/{scenario['id']}"), json={"stdin": "1\n"})  # то же значение
    assert state()["state"] == "recorded"

    client.put(url(project, f"/{scenario['id']}"), json={"stdin": "2\n"})
    session.expire_all()
    assert state()["state"] == "none"
    assert session.exec(select(Baseline)).all() == []


def test_import_with_expected_output_and_name_clashes(client, make_project):
    project = make_project()
    create(client, project, "empty")
    payload = {
        "scenarios": [
            {
                "name": "empty",
                "stdin": "0\n",
                "expected_stdout": "Заказов нет\n",
                "expected_exit_code": 0,
            },
            {"name": "two", "args": ["a"]},
        ]
    }
    result = client.post(url(project, "/import"), json=payload).json()
    assert result["imported"] == 2
    assert len(result["scenario_ids"]) == 2
    assert any("empty (2)" in w for w in result["warnings"])

    exported = {s["name"]: s for s in client.get(url(project, "/export")).json()["scenarios"]}
    assert set(exported) == {"empty", "empty (2)", "two"}
    assert exported["empty (2)"]["expected_stdout"] == "Заказов нет\n"
    assert exported["empty (2)"]["expected_exit_code"] == 0
    assert exported["two"]["args"] == ["a"]
    assert exported["two"]["expected_stdout"] is None

    imported = client.get(url(project)).json()["scenarios"]
    assert [s["source"] for s in imported] == ["manual", "imported", "imported"]


def test_export_uses_the_baseline_when_nothing_is_expected(client, make_project, session: Session):
    project = make_project()
    scenario = create(client, project, "s")
    session.add(
        Baseline(
            project_id=project["id"],
            scenario_id=scenario["id"],
            version_id=project["original_version_id"],
            stdout="из эталона",
            exit_code=3,
        )
    )
    session.commit()
    [item] = client.get(url(project, "/export")).json()["scenarios"]
    assert (item["expected_stdout"], item["expected_exit_code"]) == ("из эталона", 3)


def test_sample_scenarios_keep_expected_output(client, demo_orders):
    exported = client.get(f"/api/projects/{demo_orders['id']}/scenarios/export").json()["scenarios"]
    assert len(exported) == 11
    assert all(s["expected_stdout"] for s in exported)
    names = {s["name"] for s in exported}
    assert {"cyrillic", "uncaught-exception"} <= names
    crash = next(s for s in exported if s["name"] == "uncaught-exception")
    assert crash["expected_exit_code"] == 1


def test_import_limit_and_delete_project_cascade(client, make_project):
    project = make_project()
    many = {"scenarios": [{"name": f"s{i}"} for i in range(501)]}
    assert client.post(url(project, "/import"), json=many).status_code == 400
    create(client, project, "s")
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert client.get(url(project)).status_code == 404
