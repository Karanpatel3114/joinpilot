"""Property-based tests: invariants that must hold for any table, not just hand-picked ones."""

from collections.abc import Iterator
from contextlib import contextmanager

import duckdb
import pyarrow as pa
from hypothesis import given, settings
from hypothesis import strategies as st

from joinpilot.profiling.keys import candidate_keys
from joinpilot.profiling.normalize import choose_normalization
from joinpilot.profiling.overlap import overlap_columns, pair_counts
from joinpilot.profiling.stats import profile_columns

FAST = settings(max_examples=40, deadline=None)
codes = st.text(alphabet="0123456789AB ", min_size=0, max_size=6)


@contextmanager
def warehouse(**tables: pa.Table) -> Iterator[duckdb.DuckDBPyConnection]:
    con = duckdb.connect()
    for name, data in tables.items():
        con.register("src", data)
        con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM src')
        con.unregister("src")
    try:
        yield con
    finally:
        con.close()


@FAST
@given(st.lists(st.none() | codes, min_size=1, max_size=40))
def test_statistics_agree_with_python(values: list[str | None]) -> None:
    with warehouse(t=pa.table({"c": pa.array(values, pa.string())})) as con:
        rows, [column] = profile_columns(con, "t", sample_values=3)
    present = [v for v in values if v is not None]
    assert rows == len(values)
    assert column.null_pct == round(1 - len(present) / len(values), 6)
    assert 0.0 <= column.null_pct <= 1.0
    assert column.distinct_count == len(set(present)) <= len(present)
    assert column.is_key_candidate == (len(set(present)) == len(values))
    assert column.sample_values == sorted(set(present))[:3]
    lengths = {len(v) for v in present}
    assert column.fixed_length == (lengths.pop() if len(lengths) == 1 else None)
    assert column.digits_only == (bool(present) and all(v.isdigit() for v in present))


@FAST
@given(st.lists(st.tuples(st.integers(0, 4), st.integers(0, 4)), min_size=1, max_size=25))
def test_every_reported_key_is_really_unique(rows: list[tuple[int, int]]) -> None:
    data = pa.table({"a": [r[0] for r in rows], "b": [r[1] for r in rows]})
    with warehouse(t=data) as con:
        n, columns = profile_columns(con, "t", sample_values=1)
        keys = candidate_keys(con, "t", n, columns, max_pair_columns=12)
    for key in keys:
        values = [tuple(r[0 if c == "a" else 1] for c in key) for r in rows]
        assert len(set(values)) == len(values)
    for i, name in enumerate(("a", "b")):
        if len({r[i] for r in rows}) == len(rows):
            assert [name] in keys


@FAST
@given(
    st.sets(codes.filter(bool), min_size=1, max_size=30), st.sets(codes.filter(bool), max_size=30)
)
def test_inclusion_ratio_is_the_share_of_distinct_values_found(
    source: set[str], target: set[str]
) -> None:
    target = target | {"ZZZ"}
    with warehouse(s=pa.table({"k": sorted(source)}), t=pa.table({"k": sorted(target)})) as con:
        profiles = {name: profile_columns(con, name, 1)[1] for name in ("s", "t")}
        found = pair_counts(con, overlap_columns(profiles, 40), sample_size=1_000)
    pair = next((p for p in found if p.source.table == "s"), None)
    expected = len(source & target) / len(source)
    assert (pair.ratio("none") if pair else 0.0) == expected
    assert 0.0 <= expected <= 1.0


@FAST
@given(st.sets(st.integers(1, 99_999), min_size=1, max_size=40), st.integers(6, 12))
def test_unpadded_keys_always_pad_to_the_master_width(keys: set[int], width: int) -> None:
    master = pa.table({"id": [str(k).zfill(width) for k in sorted(keys)]})
    facts = pa.table({"id": [str(k) for k in sorted(keys)]})
    with warehouse(master=master, facts=facts) as con:
        profiles = {name: profile_columns(con, name, 1)[1] for name in ("master", "facts")}
        found = pair_counts(con, overlap_columns(profiles, 40), sample_size=1_000)
    pair = next(p for p in found if p.source.table == "facts")
    assert choose_normalization(pair, min_gain=0.1) == (f"lpad_zeros:{width}", 1.0)
