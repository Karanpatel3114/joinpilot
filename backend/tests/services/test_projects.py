import io
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from joinpilot.config import Settings
from joinpilot.errors import ConflictError, InvalidInputError, PayloadTooLargeError
from joinpilot.services.projects import ProjectService


@pytest.fixture
def service(tmp_path: Path) -> ProjectService:
    return ProjectService(Settings(_env_file=None, data_dir=tmp_path))


def test_concurrent_uploads_to_one_project_keep_every_table(service: ProjectService) -> None:
    project = service.create("Busy")

    def upload(i: int) -> None:
        csv = f"id,value\n{i},a\n{i + 100},b\n".encode()
        service.add_upload(project.id, f"table_{i}.csv", io.BytesIO(csv))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(upload, range(8)))
    names = sorted(t.name for t in service.get(project.id).tables)
    assert names == [f"table_{i}" for i in range(8)]
    profile = service.profile(project.id)
    assert len(profile.tables) == 8


def test_profile_is_recomputed_after_a_new_upload(service: ProjectService) -> None:
    project = service.create("Fresh")
    service.add_upload(project.id, "a.csv", io.BytesIO(b"k\n1\n2\n"))
    assert [t.name for t in service.profile(project.id).tables] == ["a"]
    service.add_upload(project.id, "b.csv", io.BytesIO(b"k\n1\n"))
    assert [t.name for t in service.profile(project.id).tables] == ["a", "b"]


def test_hostile_headers_are_loaded_and_profiled_safely(service: ProjectService) -> None:
    project = service.create("Hostile")
    header = '"a""; DROP TABLE x; --","naïve col","Ünïcode","x;y"\n'
    csv = (header + "1,2,3,4\n5,6,7,8\n").encode()
    [table] = service.add_upload(project.id, "weird name (1).csv", io.BytesIO(csv))
    assert table.name == "weird_name_1"
    columns = [c.name for c in service.profile(project.id).tables[0].columns]
    assert columns == ['a"; DROP TABLE x; --', "naïve col", "Ünïcode", "x;y"]


def test_table_limit_is_checked_before_loading(tmp_path: Path) -> None:
    service = ProjectService(Settings(_env_file=None, data_dir=tmp_path, max_tables_per_project=1))
    project = service.create("Small")
    service.add_upload(project.id, "a.csv", io.BytesIO(b"k\n1\n"))
    with pytest.raises(InvalidInputError, match="Too many tables"):
        service.add_upload(project.id, "b.csv", io.BytesIO(b"k\n1\n"))
    assert [t.name for t in service.get(project.id).tables] == ["a"]


def test_each_workspace_holds_a_limited_number_of_projects(tmp_path: Path) -> None:
    service = ProjectService(
        Settings(_env_file=None, data_dir=tmp_path, max_projects_per_workspace=2)
    )
    service.create("One", "w" * 16)
    service.create("Two", "w" * 16)
    with pytest.raises(ConflictError, match="already has 2 projects"):
        service.create("Three", "w" * 16)
    assert service.create("Elsewhere", "v" * 16).name == "Elsewhere"


def test_loads_are_refused_when_the_disk_is_nearly_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProjectService(Settings(_env_file=None, data_dir=tmp_path, min_free_disk_mb=500))
    project = service.create("Full")
    usage = shutil.disk_usage(tmp_path)._replace(free=100 * 1024 * 1024)
    monkeypatch.setattr(shutil, "disk_usage", lambda _: usage)
    with pytest.raises(PayloadTooLargeError, match="no room"):
        service.add_upload(project.id, "a.csv", io.BytesIO(b"k\n1\n"))
    assert service.get(project.id).tables == []
