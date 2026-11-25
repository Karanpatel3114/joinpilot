import duckdb

from joinpilot.profiling.keys import candidate_keys
from joinpilot.profiling.stats import profile_columns


def keys_of(con: duckdb.DuckDBPyConnection, table: str) -> list[list[str]]:
    rows, columns = profile_columns(con, table, sample_values=1)
    return candidate_keys(con, table, rows, columns, max_pair_columns=12)


def test_single_column_key_is_found(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE h AS SELECT range::VARCHAR AS id, range % 3 AS g FROM range(10)")
    assert keys_of(con, "h") == [["id"]]


def test_two_column_key_is_found_when_no_single_key_exists(
    con: duckdb.DuckDBPyConnection,
) -> None:
    con.execute("""
        CREATE TABLE items AS
        SELECT o::VARCHAR AS order_id, i AS item_no, (o * i) % 4 AS qty
        FROM range(20) a(o), range(1, 4) b(i)
    """)
    assert keys_of(con, "items") == [["order_id", "item_no"]]


def test_nullable_columns_are_not_part_of_composite_keys(
    con: duckdb.DuckDBPyConnection,
) -> None:
    con.execute("""
        CREATE TABLE t AS SELECT * FROM (VALUES
            ('a', 1, 'x'), ('a', 2, NULL), ('b', 1, 'y'), ('b', 2, 'z')
        ) v(k, n, label)
    """)
    assert keys_of(con, "t") == [["k", "n"]]


def test_table_without_any_key_returns_nothing(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE d AS SELECT 'same' AS a, 1 AS b FROM range(3)")
    assert keys_of(con, "d") == []
