"""Read gold files and check they belong to the data being evaluated."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from joinpilot.config import REPO_ROOT

GOLD_ROOT = REPO_ROOT / "data" / "gold"


class GoldFilter(BaseModel):
    """A filter a true join needs (for example one language)."""

    column: str
    value: str


class GoldEdge(BaseModel):
    """A true join, many side first."""

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    normalization: str
    fan_out: bool
    filter: GoldFilter | None = None


class GoldDecoy(BaseModel):
    """A column pair that looks like a join but is not."""

    a: str
    b: str
    reason: str


class GoldJoins(BaseModel):
    """All true joins and decoys of one dataset."""

    dataset_id: str
    edges: list[GoldEdge]
    decoys: list[GoldDecoy] = Field(default_factory=list)


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
