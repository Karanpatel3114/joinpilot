from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from joinpilot.errors import InvalidInputError
from joinpilot.profiling.loader import (
    WAREHOUSE_FILE,
    connect,
    list_tables,
    load_file,
    table_name_from_filename,
)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [("KNA1.csv", "KNA1"), ("vbak (2).parquet", "vbak_2"), ("2026 sales.csv", "t_2026_sales"),
     ("ümlaut-data.csv", "mlaut_data"), ("___.csv", "t_")],
)  # fmt: skip
def test_table_names_are_safe_identifiers(filename: str, expected: str) -> None:
    assert table_name_from_filename(filename) == expected


def test_connect_creates_one_duckdb_file_per_project(tmp_path: Path) -> None:
    connect(tmp_path / "p1").close()
    assert (tmp_path / "p1" / WAREHOUSE_FILE).exists()


def test_csv_keeps_leading_zeros_and_types_other_columns(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    path = tmp_path / "customers.csv"
    path.write_text(
        "id,amount,qty,since,name\n0001,1.50,3,2026-01-02,Alpha\n0002,20.25,10,2025-12-31,Beta\n"
    )
    loaded = load_file(con, path, "customers")
    assert (loaded.row_count, loaded.column_count) == (2, 5)
    types = dict(
        con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'customers'"
        ).fetchall()
    )
    assert types == {
        "id": "VARCHAR", "amount": "DECIMAL(18,2)", "qty": "BIGINT", "since": "DATE",
        "name": "VARCHAR",
    }  # fmt: skip
    assert con.execute("SELECT id FROM customers ORDER BY id").fetchall() == [("0001",), ("0002",)]


def test_parquet_is_loaded_as_is_and_reload_replaces(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    path = tmp_path / "t.parquet"
    pq.write_table(pa.table({"k": ["a", "b", "c"]}), path)
    assert load_file(con, path, "items").row_count == 3
    pq.write_table(pa.table({"k": ["a"]}), path)
    assert load_file(con, path, "items").row_count == 1
    assert list_tables(con) == ["items"]


def test_unsupported_or_broken_files_raise_invalid_input(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    with pytest.raises(InvalidInputError):
        load_file(con, tmp_path / "data.xlsx", "x")
    broken = tmp_path / "broken.parquet"
    broken.write_bytes(b"not parquet")
    with pytest.raises(InvalidInputError):
        load_file(con, broken, "x")
