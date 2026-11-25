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
        "id": "VARCHAR", "amount": "DECIMAL(4,2)", "qty": "BIGINT", "since": "DATE",
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


def test_wide_files_are_refused_before_any_table_is_created(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    csv = tmp_path / "wide.csv"
    csv.write_text(",".join(f"c{i}" for i in range(6)) + "\n" + ",".join("1" * 6) + "\n")
    parquet = tmp_path / "wide.parquet"
    pq.write_table(pa.table({f"c{i}": [1] for i in range(6)}), parquet)
    for path in (csv, parquet):
        with pytest.raises(InvalidInputError) as error:
            load_file(con, path, "wide", max_columns=5)
        assert error.value.details["columns"] == 6
    assert list_tables(con) == []


def test_empty_and_undelimited_csvs_are_explained(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(InvalidInputError, match="empty"):
        load_file(con, empty, "e")
    ragged = tmp_path / "ragged.csv"
    ragged.write_text("a,b\n1\n2,3,4,5\n6,7\n")
    with pytest.raises(InvalidInputError, match="could not be detected"):
        load_file(con, ragged, "r")


def test_huge_decimals_fall_back_to_double(con: duckdb.DuckDBPyConnection, tmp_path: Path) -> None:
    path = tmp_path / "big.csv"
    path.write_text("v\n1234567890123456789012345678901234567.5\n1.25\n")
    load_file(con, path, "big")
    [(data_type,)] = con.execute(
        "SELECT data_type FROM information_schema.columns WHERE table_name = 'big'"
    ).fetchall()
    assert data_type == "DOUBLE"


def test_errors_name_the_uploaded_file_but_never_server_paths(
    con: duckdb.DuckDBPyConnection, tmp_path: Path
) -> None:
    broken = tmp_path / "3f0b7c1e-uuid.parquet"
    broken.write_bytes(b"PAR1 definitely not parquet")
    with pytest.raises(InvalidInputError) as error:
        load_file(con, broken, "x", display_name="sales.parquet")
    text = str(error.value.details)
    assert error.value.details["file"] == "sales.parquet"
    assert str(tmp_path) not in text and "uuid" not in text


def test_connections_use_the_configured_limits(tmp_path: Path) -> None:
    with connect(tmp_path / "p", memory_limit="256MB", threads=1) as con:
        limit, threads = con.execute(
            "SELECT current_setting('memory_limit'), current_setting('threads')"
        ).fetchone()  # type: ignore[misc]
    assert threads == 1
    assert "MiB" in limit or "MB" in limit
