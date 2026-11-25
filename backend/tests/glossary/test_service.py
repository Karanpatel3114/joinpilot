import io
import os
from pathlib import Path

import pytest

from joinpilot.config import Settings
from joinpilot.glossary.service import GlossaryService, describe
from joinpilot.services.projects import ProjectService


def service_with(settings: Settings, sample: str) -> tuple[GlossaryService, str]:
    projects = ProjectService(settings)
    project = projects.create("Glossary")
    projects.add_sample(project.id, sample)
    return GlossaryService(settings), project.id


@pytest.fixture
def sqlite_settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path)


def top(glossary: GlossaryService, project_id: str, query: str, k: int = 3) -> list[str]:
    return [m.column for m in glossary.search(project_id, query, k)]


def test_sap_columns_are_described_in_business_words() -> None:
    assert describe("KNA1", "KUNNR") == "customer number of customer master (KNA1.KUNNR)"
    assert describe("orders", "product_group") == "product group of orders (orders.product_group)"


def test_business_words_find_cryptic_sap_columns(sqlite_settings: Settings) -> None:
    glossary, project = service_with(sqlite_settings, "erp_s1_sap")
    assert "KNA1.NAME1" in top(glossary, project, "customer name")
    assert "BSID.DMBTR" in top(glossary, project, "open receivable amount")
    assert top(glossary, project, "sales order number", 1)[0] in {"VBAK.VBELN", "VBAP.VBELN"}
    best = glossary.search(project, "customer name", 1)[0]
    assert 0 < best.score <= 1


def test_friendly_names_work_without_hints(sqlite_settings: Settings) -> None:
    glossary, project = service_with(sqlite_settings, "erp_s1_friendly")
    assert top(glossary, project, "product group", 1) == ["products.product_group"]


def test_new_uploads_rebuild_the_glossary(sqlite_settings: Settings) -> None:
    glossary, project = service_with(sqlite_settings, "erp_s1_sap")
    glossary.search(project, "customer", 1)
    ProjectService(sqlite_settings).add_upload(
        project, "warehouses.csv", io.BytesIO(b"warehouse_code,city\nW1,Berlin\n")
    )
    assert top(glossary, project, "warehouse code", 1) == ["warehouses.warehouse_code"]


@pytest.mark.integration
def test_pgvector_search_matches_the_python_search(
    tmp_path: Path, sqlite_settings: Settings
) -> None:
    url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://joinpilot:joinpilot@localhost:5432/joinpilot"
    )
    postgres = Settings(_env_file=None, data_dir=tmp_path / "pg", database_url=url)
    pg_glossary, pg_project = service_with(postgres, "erp_s1_sap")
    py_glossary, py_project = service_with(sqlite_settings, "erp_s1_sap")
    for query in ("customer name", "open receivable amount", "product group"):
        pg = pg_glossary.search(pg_project, query, 3)
        py = py_glossary.search(py_project, query, 3)
        assert [m.column for m in pg] == [m.column for m in py]
        assert all(abs(a.score - b.score) < 1e-3 for a, b in zip(pg, py, strict=True))


def test_queries_without_words_match_nothing(sqlite_settings: Settings) -> None:
    glossary, project = service_with(sqlite_settings, "erp_s1_sap")
    assert glossary.search(project, "!!!", 3) == []


def test_concurrent_searches_build_the_glossary_once(sqlite_settings: Settings) -> None:
    from concurrent.futures import ThreadPoolExecutor

    glossary, project = service_with(sqlite_settings, "erp_s1_sap")
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: top(glossary, project, "customer name"), range(6)))
    assert all(r == results[0] for r in results)
    assert len(set(results[0])) == len(results[0]) == 3
    assert glossary._count(project) == 35
