import duckdb

from joinpilot.profiling.stats import profile_columns


def test_column_statistics_describe_nulls_distincts_and_shape(
    con: duckdb.DuckDBPyConnection,
) -> None:
    con.execute("""
        CREATE TABLE t AS SELECT * FROM (VALUES
            ('0001', 'x', 10.5, NULL),
            ('0002', 'x', 11.0, 7),
            ('0003', 'yy', 12.0, 7),
            ('0004', NULL, 12.0, 8)
        ) v(id, code, amount, n)
    """)
    rows, columns = profile_columns(con, "t", sample_values=2)
    by_name = {c.name: c for c in columns}
    assert rows == 4
    ident = by_name["id"]
    assert (ident.null_pct, ident.distinct_count, ident.is_key_candidate) == (0.0, 4, True)
    assert (ident.fixed_length, ident.digits_only) == (4, True)
    assert ident.sample_values == ["0001", "0002"]
    code = by_name["code"]
    assert (code.null_pct, code.distinct_count, code.is_key_candidate) == (0.25, 2, False)
    assert (code.fixed_length, code.max_length) == (None, 2)
    assert by_name["n"].null_pct == 0.25
    assert by_name["amount"].is_key_candidate is False


def test_unique_decimal_columns_are_never_key_candidates(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE m AS SELECT CAST(range AS DECIMAL(10,2)) AS amount FROM range(5)")
    _, columns = profile_columns(con, "m", sample_values=3)
    assert columns[0].distinct_count == 5
    assert columns[0].is_key_candidate is False


def test_empty_table_has_zero_rows_and_no_keys(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE e (id VARCHAR)")
    rows, columns = profile_columns(con, "e", sample_values=5)
    assert rows == 0
    assert columns[0].is_key_candidate is False
    assert columns[0].sample_values == []
