"""Read gold files and check they belong to the data being evaluated."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from joinpilot.config import REPO_ROOT

GOLD_ROOT = REPO_ROOT / "data" / "gold"
STRICT = ConfigDict(extra="forbid", populate_by_name=True)


class GoldFilter(BaseModel):
    """A filter a true join needs (for example one language)."""

    model_config = STRICT

    column: str
    value: str


class GoldEdge(BaseModel):
    """A true single-column join, many side first."""

    model_config = STRICT

    from_: str = Field(alias="from")
    to: str
    cardinality: str
    normalization: str
    fan_out: bool
    filter: GoldFilter | None = None
    orphan_rows: int = 0
    null_rows: int = 0


class GoldCompositeEdge(BaseModel):
    """A true join on two or more columns (for example TPC-H lineitem to partsupp)."""

    model_config = STRICT

    from_: list[str] = Field(alias="from")
    to: list[str]

    @property
    def label(self) -> tuple[str, str]:
        """The edge as a pair of `a+b` strings, for reports."""
        return "+".join(self.from_), "+".join(self.to)


class GoldDecoy(BaseModel):
    """A column pair that looks like a join but is not."""

    model_config = STRICT

    a: str
    b: str
    reason: str


class GoldJoins(BaseModel):
    """All true joins and decoys of one dataset."""

    model_config = STRICT

    dataset_id: str
    edges: list[GoldEdge]
    composite_edges: list[GoldCompositeEdge] = Field(default_factory=list)
    decoys: list[GoldDecoy] = Field(default_factory=list)
    duplicate_customers: list[list[str]] = Field(default_factory=list)


def gold_dir(dataset_id: str, root: Path = GOLD_ROOT) -> Path:
    """Folder that holds one dataset's gold files."""
    return root / dataset_id


def load_joins(dataset_id: str, root: Path = GOLD_ROOT) -> GoldJoins:
    """The true join edges and decoys of one dataset."""
    return GoldJoins.model_validate_json((gold_dir(dataset_id, root) / "joins.json").read_text())


def load_manifest(dataset_id: str, root: Path = GOLD_ROOT) -> dict[str, Any] | None:
    """Gold provenance (fingerprint, generator version, settings), if recorded."""
    path = gold_dir(dataset_id, root) / "manifest.json"
    if not path.exists():
        return None
    manifest: dict[str, Any] = json.loads(path.read_text())
    return manifest


def load_kpis(dataset_id: str, root: Path = GOLD_ROOT) -> dict[str, Any] | None:
    """The true KPI values of an ERP dataset (TPC-H has none)."""
    path = gold_dir(dataset_id, root) / "kpis.json"
    if not path.exists():
        return None
    kpis: dict[str, Any] = json.loads(path.read_text())
    return kpis
