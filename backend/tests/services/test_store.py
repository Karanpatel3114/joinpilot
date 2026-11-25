from pathlib import Path

import pytest

from joinpilot.errors import NotFoundError
from joinpilot.services.store import ProjectStore, TableRecord


def test_projects_round_trip_through_json_files(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path)
    first = store.create("First")
    second = store.create("Second")
    second.tables.append(TableRecord(table_id="t1", name="KNA1", row_count=3, column_count=2))
    store.save(second)
    assert store.get(second.id).tables[0].name == "KNA1"
    assert [p.id for p in store.list_projects()] == [second.id, first.id]


@pytest.mark.parametrize(
    "project_id", ["not-a-uuid", "../../etc", "8a5b2c3e-0000-4000-8000-000000000000"]
)
def test_unknown_or_malformed_ids_are_not_found(tmp_path: Path, project_id: str) -> None:
    with pytest.raises(NotFoundError):
        ProjectStore(tmp_path).get(project_id)


def test_empty_root_lists_nothing(tmp_path: Path) -> None:
    assert ProjectStore(tmp_path / "missing").list_projects() == []
