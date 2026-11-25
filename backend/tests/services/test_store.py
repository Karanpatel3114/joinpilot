import time
from pathlib import Path

import pytest

from joinpilot.errors import NotFoundError
from joinpilot.services.store import ProjectStore, TableRecord


@pytest.fixture
def store(tmp_path: Path) -> ProjectStore:
    return ProjectStore(tmp_path / "projects", f"sqlite:///{tmp_path / 'app.db'}")


def test_projects_and_their_tables_round_trip(store: ProjectStore) -> None:
    first = store.create("First")
    time.sleep(0.01)
    second = store.create("Second")
    second.tables = [
        TableRecord(table_id="t1", name="KNA1", row_count=3, column_count=2),
        TableRecord(table_id="t2", name="BSID", row_count=5, column_count=4),
    ]
    store.save(second)
    loaded = store.get(second.id)
    assert {t.name for t in loaded.tables} == {"KNA1", "BSID"}
    assert loaded.created_at.tzinfo is not None
    assert [p.id for p in store.list_projects()] == [second.id, first.id]


def test_saving_replaces_updates_and_removes_tables(store: ProjectStore) -> None:
    project = store.create("P")
    project.tables = [TableRecord(table_id="t1", name="A", row_count=1, column_count=1)]
    store.save(project)
    project.tables = [
        TableRecord(table_id="t1", name="A", row_count=9, column_count=2),
        TableRecord(table_id="t3", name="C", row_count=1, column_count=1),
    ]
    store.save(project)
    tables = {t.table_id: t for t in store.get(project.id).tables}
    assert set(tables) == {"t1", "t3"} and tables["t1"].row_count == 9


@pytest.mark.parametrize(
    "project_id", ["not-a-uuid", "../../etc", "8a5b2c3e-0000-4000-8000-000000000000"]
)
def test_unknown_or_malformed_ids_are_not_found(store: ProjectStore, project_id: str) -> None:
    with pytest.raises(NotFoundError):
        store.get(project_id)


def test_an_empty_database_lists_nothing(store: ProjectStore) -> None:
    assert store.list_projects() == []


@pytest.mark.integration
def test_store_works_on_postgres(tmp_path: Path) -> None:
    import os

    url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://joinpilot:joinpilot@localhost:5432/joinpilot"
    )
    store = ProjectStore(tmp_path, url)
    project = store.create("On Postgres")
    project.tables = [
        TableRecord(table_id=f"pg-{project.id[:8]}", name="KNA1", row_count=1, column_count=1)
    ]
    store.save(project)
    assert store.get(project.id).tables[0].name == "KNA1"
    assert project.id in {p.id for p in store.list_projects()}
