"""Profile every table of a project and assign stable evidence ids."""

from __future__ import annotations

import logging
import time

import duckdb

from joinpilot.config import ProfilingSettings
from joinpilot.profiling.keys import candidate_keys
from joinpilot.profiling.models import (
    ColumnProfile,
    KeyEvidence,
    Overlap,
    ProjectProfile,
    TableProfile,
    is_key_like_type,
)
from joinpilot.profiling.normalize import choose_normalization
from joinpilot.profiling.overlap import overlap_columns, pair_counts
from joinpilot.profiling.stats import profile_columns

logger = logging.getLogger(__name__)


def key_evidence(
    table: str, columns: list[ColumnProfile], row_count: int, keys: list[list[str]]
) -> list[KeyEvidence]:
    """Uniqueness of every integer or text column, and of each composite key."""
    evidence = []
    for column in columns:
        if not is_key_like_type(column.type):
            continue
        non_null = column.non_null_count
        evidence.append(
            KeyEvidence(
                evidence_id="",
                table=table,
                columns=[column.name],
                distinct_count=column.distinct_count,
                non_null_count=non_null,
                uniqueness=min(1.0, round(column.distinct_count / non_null, 6))
                if non_null
                else 0.0,
            )
        )
    for key in keys:
        if len(key) > 1:
            evidence.append(
                KeyEvidence(
                    evidence_id="",
                    table=table,
                    columns=key,
                    distinct_count=row_count,
                    non_null_count=row_count,
                    uniqueness=1.0,
                )
            )
    return evidence


def profile_project(
    con: duckdb.DuckDBPyConnection, tables: dict[str, str], settings: ProfilingSettings
) -> ProjectProfile:
    """Profile `tables` (table_id -> name) and compute overlaps between them."""
    started = time.perf_counter()
    table_profiles: list[TableProfile] = []
    keys: list[KeyEvidence] = []
    columns_by_table: dict[str, list[ColumnProfile]] = {}
    for table_id, name in sorted(tables.items(), key=lambda kv: kv[1]):
        row_count, columns = profile_columns(con, name, settings.sample_values)
        table_keys = candidate_keys(con, name, row_count, columns, settings.max_pair_columns)
        table_profiles.append(
            TableProfile(
                table_id=table_id,
                name=name,
                row_count=row_count,
                columns=columns,
                candidate_keys=table_keys,
            )
        )
        keys += key_evidence(name, columns, row_count, table_keys)
        columns_by_table[name] = columns

    refs = overlap_columns(columns_by_table, settings.overlap_max_value_length)
    overlaps = []
    for pair in pair_counts(con, refs, settings.overlap_sample_size):
        normalization, ratio = choose_normalization(pair, settings.normalization_min_gain)
        if ratio < settings.overlap_min_ratio:
            continue
        overlaps.append(
            Overlap(
                evidence_id="",
                from_=pair.source.qualified,
                to=pair.target.qualified,
                inclusion_ratio=round(ratio, 6),
                raw_inclusion_ratio=round(pair.ratio("none"), 6),
                normalization=normalization,
                checked_values=pair.checked,
                matched_values=round(ratio * pair.checked),
                sampled=pair.sampled,
            )
        )
    keys.sort(key=lambda k: (k.table, k.columns))
    overlaps.sort(key=lambda o: (o.from_, o.to))
    for i, key in enumerate(keys, start=1):
        key.evidence_id = f"uk_{i:03d}"
    for i, overlap in enumerate(overlaps, start=1):
        overlap.evidence_id = f"ov_{i:03d}"
    elapsed = time.perf_counter() - started
    logger.info("profiled %d tables, %d overlaps in %.2fs", len(tables), len(overlaps), elapsed)
    return ProjectProfile(tables=table_profiles, keys=keys, overlaps=overlaps)
