"""Join candidates and the evidence-backed features behind their scores."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Cardinality = Literal["N:1", "1:1", "1:N", "N:M"]


class JoinFilter(BaseModel):
    """A filter that removes fan-out, such as keeping one language of a text table."""

    column: str
    value: str
    choices: list[str]


class JoinCandidate(BaseModel):
    """One directed column pair (many side first) that might be a join."""

    model_config = ConfigDict(populate_by_name=True)

    edge_id: str = ""
    from_: str = Field(alias="from")
    to: str
    normalization: str = "none"
    inclusion_ratio: float = Field(ge=0.0, le=1.0)
    coverage_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    target_uniqueness: float = Field(default=0.0, ge=0.0, le=1.0)
    source_uniqueness: float = Field(default=0.0, ge=0.0, le=1.0)
    target_distinct: int = 0
    name_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    cardinality: Cardinality = "N:M"
    fan_out_risk: bool = False
    rows_per_key: float = 1.0
    filter: JoinFilter | None = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    accepted: bool = False
    rejection_reason: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    # Which evidence id plays which role: inclusion, coverage, target_uniqueness,
    # source_uniqueness, fan_out_key.
    evidence_roles: dict[str, str] = Field(default_factory=dict)

    @property
    def source_table(self) -> str:
        """Table of the many side."""
        return self.from_.split(".", 1)[0]

    @property
    def target_table(self) -> str:
        """Table of the one side."""
        return self.to.split(".", 1)[0]
