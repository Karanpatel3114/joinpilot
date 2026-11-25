import duckdb
import pytest

from joinpilot.profiling.normalize import choose_normalization, normalized_sql
from joinpilot.profiling.overlap import PairCounts, overlap_columns, pair_counts
from joinpilot.profiling.stats import profile_columns


def pairs(con: duckdb.DuckDBPyConnection) -> dict[tuple[str, str], PairCounts]:
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    profiles = {t: profile_columns(con, t, sample_values=1)[1] for t in tables}
    refs = overlap_columns(profiles, max_value_length=40)
    found = pair_counts(con, refs, sample_size=1_000)
    return {(p.source.qualified, p.target.qualified): p for p in found}


def test_stripped_zeros_against_a_fixed_width_master_become_lpad(
    con: duckdb.DuckDBPyConnection,
) -> None:
    con.execute(
        "CREATE TABLE kna1 AS "
        "SELECT lpad((100000 + range)::VARCHAR, 10, '0') AS kunnr FROM range(50)"
    )
    con.execute(
        "CREATE TABLE bsid AS SELECT (100000 + range % 40)::VARCHAR AS kunnr FROM range(80)"
    )
    pair = pairs(con)[("bsid.kunnr", "kna1.kunnr")]
    assert pair.ratio("none") == 0.0
    assert choose_normalization(pair, min_gain=0.1) == ("lpad_zeros:10", 1.0)


def test_integer_keys_match_zero_padded_text_keys(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        "CREATE TABLE master AS SELECT lpad(range::VARCHAR, 6, '0') AS id FROM range(1, 30)"
    )
    con.execute("CREATE TABLE facts AS SELECT (range % 29) + 1 AS id FROM range(60)")
    assert choose_normalization(pairs(con)[("facts.id", "master.id")], 0.1) == ("lpad_zeros:6", 1.0)


def test_variable_width_targets_strip_zeros_on_both_sides(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE a AS SELECT * FROM (VALUES ('007'), ('0042'), ('9')) v(k)")
    con.execute("CREATE TABLE b AS SELECT * FROM (VALUES ('7'), ('42'), ('0009'), ('5')) v(k)")
    assert choose_normalization(pairs(con)[("a.k", "b.k")], 0.1) == ("strip_leading_zeros", 1.0)


def test_case_and_whitespace_differences_become_trim_upper(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE a AS SELECT * FROM (VALUES (' de'), ('fr '), ('Us')) v(code)")
    con.execute("CREATE TABLE b AS SELECT * FROM (VALUES ('DE'), ('FR'), ('US'), ('IN')) v(code)")
    assert choose_normalization(pairs(con)[("a.code", "b.code")], 0.1) == ("trim_upper", 1.0)


def test_raw_matches_keep_no_normalization(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE a AS SELECT lpad(range::VARCHAR, 4, '0') AS k FROM range(10)")
    con.execute("CREATE TABLE b AS SELECT lpad(range::VARCHAR, 4, '0') AS k FROM range(20)")
    assert choose_normalization(pairs(con)[("a.k", "b.k")], 0.1) == ("none", 1.0)


def test_small_gains_do_not_justify_a_normalization(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE TABLE a AS SELECT * FROM (VALUES ('A1'), ('A2'), ('A3'), ('a4')) v(k)")
    con.execute("CREATE TABLE b AS SELECT * FROM (VALUES ('A1'), ('A2'), ('A3'), ('A4')) v(k)")
    pair = pairs(con)[("a.k", "b.k")]
    assert choose_normalization(pair, min_gain=0.5) == ("none", 0.75)


@pytest.mark.parametrize(
    ("normalization", "side", "expected"),
    [
        ("none", "from", '"t"."k"'),
        ("lpad_zeros:10", "from", """lpad(CAST("t"."k" AS VARCHAR), 10, '0')"""),
        ("lpad_zeros:10", "to", '"t"."k"'),
        ("strip_leading_zeros", "to", """ltrim(CAST("t"."k" AS VARCHAR), '0')"""),
        ("trim_upper", "from", 'upper(trim(CAST("t"."k" AS VARCHAR)))'),
    ],
)
def test_recorded_normalizations_become_join_expressions(
    normalization: str, side: str, expected: str
) -> None:
    assert normalized_sql('"t"."k"', normalization, side) == expected  # type: ignore[arg-type]


def test_unknown_normalization_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown normalization"):
        normalized_sql("k", "reverse", "from")
