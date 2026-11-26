import json
from typing import Any

import duckdb
import pytest
import sqlglot

from joinpilot.config import REPO_ROOT
from joinpilot.sqlgen.export import DIALECTS, export_script, export_sql, export_views

VIEWS: list[dict[str, Any]] = json.loads(
    (REPO_ROOT / "shared" / "fixtures" / "views.json").read_text()
)


@pytest.mark.parametrize("dialect", DIALECTS)
def test_every_view_exports_to_sql_that_parses_back(dialect: str) -> None:
    for view in VIEWS:
        sql, _ = export_sql(view["sql"], dialect)  # type: ignore[arg-type]
        assert sqlglot.parse_one(sql, read=dialect) is not None


def test_duckdb_only_date_parsing_becomes_each_dialects_own() -> None:
    vbap = next(v for v in VIEWS if v["name"] == "v_vbap")
    assert "TRY_TO_TIMESTAMP" in export_sql(vbap["sql"], "snowflake")[0]
    assert "SAFE_CAST" in export_sql(vbap["sql"], "bigquery")[0]
    postgres, notes = export_sql(vbap["sql"], "postgres")
    assert "TO_TIMESTAMP" in postgres and "no safe date parsing" in notes[0]
    assert "`v_vbap`" in export_sql(vbap["sql"], "bigquery")[0]


def test_views_and_scripts_carry_the_dialect_and_notes() -> None:
    exported = export_views(VIEWS, "snowflake")
    assert {v["dialect"] for v in exported} == {"snowflake"}
    script = export_script(VIEWS, "postgres", "run-1")
    assert script.startswith("-- JoinPilot data model for run run-1, postgres dialect")
    assert script.count("CREATE OR REPLACE VIEW") == len(VIEWS)
    assert "-- Note: Postgres has no safe date parsing" in script


def test_the_duckdb_script_runs_against_the_raw_tables(
    sample_duckdb: duckdb.DuckDBPyConnection,
) -> None:
    sample_duckdb.execute("CREATE SCHEMA IF NOT EXISTS model")
    for statement in export_script(VIEWS, "duckdb", "r").split(";\n"):
        if statement.strip() and not statement.strip().startswith("--"):
            sample_duckdb.execute(statement.split("\n\n")[-1])
    assert sample_duckdb.execute("SELECT COUNT(*) FROM model.v_vbap").fetchone() == (30116,)


def test_pretty_duckdb_sql_returns_exactly_the_rows_of_the_sql_that_ran(
    sample_duckdb: duckdb.DuckDBPyConnection,
) -> None:
    sample_duckdb.execute("CREATE SCHEMA IF NOT EXISTS model")
    for view in VIEWS:
        pretty, notes = export_sql(view["sql"], "duckdb")
        assert not notes and pretty != view["sql"]
        name = f'model."{view["name"]}"'
        sample_duckdb.execute(view["sql"])
        ran = sample_duckdb.execute(f"SELECT * FROM {name} ORDER BY ALL").fetchall()
        sample_duckdb.execute(pretty)
        assert sample_duckdb.execute(f"SELECT * FROM {name} ORDER BY ALL").fetchall() == ran
