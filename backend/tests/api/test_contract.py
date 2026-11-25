"""Every example response in shared/fixtures must match the backend schemas exactly."""

import json
from typing import Any

import pytest
from pydantic import TypeAdapter

from joinpilot.api.schemas import (
    ErrorResponse,
    GlossaryMatch,
    HealthResponse,
    Project,
    ProjectProfile,
    Run,
    RunProposal,
    TableSummary,
)
from joinpilot.config import REPO_ROOT

FIXTURES_DIR = REPO_ROOT / "shared" / "fixtures"
FIXTURES: dict[str, Any] = {
    "health.json": HealthResponse,
    "error.json": ErrorResponse,
    "projects.json": list[Project],
    "tables.json": list[TableSummary],
    "profile.json": ProjectProfile,
    "run.json": Run,
    "runs.json": list[Run],
    "proposals.json": list[RunProposal],
    "glossary.json": list[GlossaryMatch],
}


def test_every_fixture_has_a_schema() -> None:
    assert {p.name for p in FIXTURES_DIR.glob("*.json")} == set(FIXTURES)


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_validates_and_round_trips(name: str) -> None:
    raw = (FIXTURES_DIR / name).read_text(encoding="utf-8")
    adapter: TypeAdapter[Any] = TypeAdapter(FIXTURES[name])
    parsed = adapter.validate_json(raw, strict=False)
    dumped = adapter.dump_python(parsed, mode="json", by_alias=True)
    assert dumped == json.loads(raw)
