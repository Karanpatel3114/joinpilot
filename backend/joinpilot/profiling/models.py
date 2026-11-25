"""Profiling results. These shapes are part of the API contract (docs/contract.md)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

INTEGER_TYPES = {"TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "UTINYINT",
                 "USMALLINT", "UINTEGER", "UBIGINT", "UHUGEINT"}  # fmt: skip
TEXT_TYPES = {"VARCHAR"}


def is_key_like_type(data_type: str) -> bool:
    """Keys are integers or text; dates, decimals and floats are never treated as keys."""
    return data_type in INTEGER_TYPES or data_type in TEXT_TYPES


class ColumnProfile(BaseModel):
    name: str
    type: str
    null_pct: float = Field(ge=0.0, le=1.0)
    non_null_count: int = Field(ge=0)
    distinct_count: int = Field(ge=0)
    sample_values: list[str]
    is_key_candidate: bool
    min_value: str | None = None
    max_value: str | None = None
    max_length: int | None = None
    fixed_length: int | None = None
    digits_only: bool = False


class TableProfile(BaseModel):
    table_id: str
    name: str
    row_count: int
    columns: list[ColumnProfile]
    candidate_keys: list[list[str]]


class KeyEvidence(BaseModel):
    """How unique a column (or column pair) is: the evidence behind `uk_` ids."""

    evidence_id: str
    table: str
    columns: list[str]
    distinct_count: int
    non_null_count: int
    uniqueness: float = Field(ge=0.0, le=1.0)


class Overlap(BaseModel):
    """Share of `from` values found in `to`: the evidence behind `ov_` ids."""

    model_config = ConfigDict(populate_by_name=True)

    evidence_id: str
    from_: str = Field(alias="from")
    to: str
    inclusion_ratio: float = Field(ge=0.0, le=1.0)
    raw_inclusion_ratio: float = Field(ge=0.0, le=1.0)
    normalization: str
    checked_values: int
    matched_values: int
    sampled: bool


class ProjectProfile(BaseModel):
    tables: list[TableProfile]
    keys: list[KeyEvidence]
    overlaps: list[Overlap]
