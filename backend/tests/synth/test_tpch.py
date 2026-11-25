from pathlib import Path

import duckdb
import pytest

from joinpilot.synth.tpch import (
    TPCH_FOREIGN_KEYS,
    TPCH_TABLES,
    dataset_id,
    generate_tpch,
    tpch_gold,
)


def test_dataset_id_formats_the_scale_factor() -> None:
    assert dataset_id(0.1) == "tpch_sf0.1"
    assert dataset_id(1.0) == "tpch_sf1"


def test_gold_graph_covers_every_table_and_points_at_primary_keys() -> None:
    gold = tpch_gold(0.1)
    tables = {e["from"].split(".")[0] for e in gold["edges"]}
    tables |= {e["to"].split(".")[0] for e in gold["edges"]}
    assert tables == set(TPCH_TABLES)
    assert all(e["to"].split(".")[1].endswith("key") for e in gold["edges"])
    assert len(gold["composite_edges"]) == 1


@pytest.mark.integration
def test_generated_tables_satisfy_every_gold_foreign_key(tmp_path: Path) -> None:
    generate_tpch(0.01, tmp_path)
    con = duckdb.connect()
    for table in TPCH_TABLES:
        con.execute(
            f"CREATE VIEW {table} AS SELECT * FROM '{(tmp_path / table).as_posix()}.parquet'"
        )
    for source, target in TPCH_FOREIGN_KEYS:
        st, sc = source.split(".")
        tt, tc = target.split(".")
        missing = con.execute(
            f"SELECT COUNT(*) FROM {st} WHERE {sc} NOT IN (SELECT {tc} FROM {tt})"
        ).fetchone()
        assert missing == (0,), source
