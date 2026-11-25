import duckdb

from joinpilot.profiling.overlap import ColumnRef, overlap_columns, pair_counts
from joinpilot.profiling.stats import profile_columns


def refs_for(con: duckdb.DuckDBPyConnection, *tables: str, max_len: int = 40) -> list[ColumnRef]:
    profiles = {t: profile_columns(con, t, sample_values=1)[1] for t in tables}
    return overlap_columns(profiles, max_value_length=max_len)


def setup(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE cust AS SELECT lpad(range::VARCHAR, 4, '0') AS id FROM range(100)")
    con.execute("""
        CREATE TABLE orders AS
        SELECT range AS order_no, lpad((range % 50)::VARCHAR, 4, '0') AS cust_id,
               CAST(range AS DECIMAL(10, 2)) AS amount
        FROM range(200)
    """)


def test_foreign_key_values_are_fully_included_in_the_master(
    con: duckdb.DuckDBPyConnection,
) -> None:
    setup(con)
    counts = {(p.source.qualified, p.target.qualified): p for p in pair_counts(
        con, refs_for(con, "cust", "orders"), sample_size=1_000)}  # fmt: skip
    forward = counts[("orders.cust_id", "cust.id")]
    assert (forward.checked, forward.ratio("none"), forward.sampled) == (50, 1.0, False)
    assert counts[("cust.id", "orders.cust_id")].ratio("none") == 0.5


def test_same_table_pairs_and_decimal_columns_are_skipped(
    con: duckdb.DuckDBPyConnection,
) -> None:
    setup(con)
    refs = refs_for(con, "cust", "orders")
    assert "orders.amount" not in {r.qualified for r in refs}
    pairs = pair_counts(con, refs, sample_size=1_000)
    assert all(p.source.table != p.target.table for p in pairs)


def test_large_columns_are_sampled_deterministically(con: duckdb.DuckDBPyConnection) -> None:
    setup(con)
    refs = refs_for(con, "cust", "orders")
    first = pair_counts(con, refs, sample_size=10)
    second = pair_counts(con, refs, sample_size=10)
    sampled = next(p for p in first if p.source.qualified == "cust.id")
    assert (sampled.checked, sampled.sampled) == (10, True)
    assert [p.matched for p in first] == [p.matched for p in second]


def test_long_text_columns_are_not_compared(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE notes AS SELECT repeat('x', 50) AS body")
    assert refs_for(con, "notes", max_len=40) == []


def test_column_cap_keeps_the_most_key_like_columns(con: duckdb.DuckDBPyConnection) -> None:
    setup(con)
    profiles = {t: profile_columns(con, t, sample_values=1)[1] for t in ("cust", "orders")}
    kept = overlap_columns(profiles, max_value_length=40, max_columns=2)
    assert [r.qualified for r in kept] == ["cust.id", "orders.order_no"]
