from collections.abc import Iterator

import duckdb
import pytest

from joinpilot.config import ProfilingSettings, SynthSettings
from joinpilot.profiling.models import ProjectProfile
from joinpilot.profiling.service import profile_project
from joinpilot.synth.dataset import build_dataset

SETTINGS = ProfilingSettings()


@pytest.fixture(scope="module")
def warehouse() -> Iterator[tuple[duckdb.DuckDBPyConnection, dict[str, str]]]:
    con = duckdb.connect()
    tables = build_dataset(1, "S", "sap", SynthSettings()).output_tables()
    for name, data in tables.items():
        con.register("src", data)
        con.execute(f'CREATE TABLE "{name}" AS SELECT * FROM src')
        con.unregister("src")
    yield con, {f"id-{name}": name for name in tables}
    con.close()


@pytest.fixture(scope="module")
def profile(warehouse: tuple[duckdb.DuckDBPyConnection, dict[str, str]]) -> ProjectProfile:
    return profile_project(*warehouse, SETTINGS)


def test_every_table_is_profiled_with_its_keys(profile: ProjectProfile) -> None:
    keys = {t.name: t.candidate_keys for t in profile.tables}
    assert keys == {
        "BSID": [["BELNR", "BUZEI"]], "KNA1": [["KUNNR"]], "MAKT": [["MATNR", "SPRAS"]],
        "MARA": [["MATNR"]], "VBAK": [["VBELN"]], "VBAP": [["VBELN", "POSNR"]],
    }  # fmt: skip
    assert {t.table_id for t in profile.tables} == {f"id-{n}" for n in keys}


def test_evidence_ids_are_sequential_and_sorted(profile: ProjectProfile) -> None:
    assert [k.evidence_id for k in profile.keys] == [
        f"uk_{i:03d}" for i in range(1, len(profile.keys) + 1)
    ]
    assert [o.evidence_id for o in profile.overlaps] == [
        f"ov_{i:03d}" for i in range(1, len(profile.overlaps) + 1)
    ]
    assert [(o.from_, o.to) for o in profile.overlaps] == sorted(
        (o.from_, o.to) for o in profile.overlaps
    )


def test_uniqueness_evidence_covers_columns_and_composite_keys(profile: ProjectProfile) -> None:
    by_columns = {(k.table, tuple(k.columns)): k for k in profile.keys}
    assert by_columns[("KNA1", ("KUNNR",))].uniqueness == 1.0
    assert by_columns[("MAKT", ("MATNR", "SPRAS"))].uniqueness == 1.0
    assert by_columns[("MAKT", ("MATNR",))].uniqueness == 0.5
    assert ("VBAK", ("NETWR",)) not in by_columns


def test_leading_zero_mismatch_is_found_and_recorded(profile: ProjectProfile) -> None:
    overlap = next(o for o in profile.overlaps if (o.from_, o.to) == ("BSID.KUNNR", "KNA1.KUNNR"))
    assert overlap.normalization == "lpad_zeros:10"
    assert overlap.raw_inclusion_ratio == 0.0
    assert overlap.inclusion_ratio > 0.95


def test_weak_overlaps_are_dropped_and_results_are_deterministic(
    warehouse: tuple[duckdb.DuckDBPyConnection, dict[str, str]], profile: ProjectProfile
) -> None:
    assert all(o.inclusion_ratio >= SETTINGS.overlap_min_ratio for o in profile.overlaps)
    again = profile_project(*warehouse, SETTINGS)
    assert again.model_dump_json() == profile.model_dump_json()


def test_uniqueness_uses_exact_non_null_counts() -> None:
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE big AS "
        "SELECT CASE WHEN range = 0 THEN NULL ELSE range END AS id FROM range(1_500_001)"
    )
    profile = profile_project(con, {"t": "big"}, SETTINGS)
    [key] = [k for k in profile.keys if k.columns == ["id"]]
    assert (key.non_null_count, key.uniqueness) == (1_500_000, 1.0)
    assert profile.tables[0].columns[0].non_null_count == 1_500_000


def test_overlap_results_are_capped_keeping_the_strongest(
    warehouse: tuple[duckdb.DuckDBPyConnection, dict[str, str]],
) -> None:
    capped = profile_project(*warehouse, ProfilingSettings(overlap_max_results=3))
    assert len(capped.overlaps) == 3
    assert all(o.inclusion_ratio == 1.0 for o in capped.overlaps)
    assert [o.evidence_id for o in capped.overlaps] == ["ov_001", "ov_002", "ov_003"]
