from collections.abc import Iterator
from datetime import date

import duckdb
import pytest

from joinpilot.agent.ranking import to_proposal
from joinpilot.config import (
    AgentSettings,
    JoinSettings,
    KPISettings,
    ProfilingSettings,
    SynthSettings,
)
from joinpilot.joins.scoring import score_candidates
from joinpilot.profiling.loader import load_arrow
from joinpilot.profiling.models import ProjectProfile
from joinpilot.profiling.service import profile_project
from joinpilot.sqlgen.views import ViewSpec, create_views, plan_views
from joinpilot.synth.dataset import build_dataset

KPI = KPISettings(reference_date=date(2026, 6, 30))
REQUIREMENT = "Open receivables by customer and aging bucket, plus 2026 revenue by product group"
Model = tuple[duckdb.DuckDBPyConnection, ProjectProfile, list[ViewSpec]]


@pytest.fixture(scope="module")
def model() -> Iterator[Model]:
    """The sap sample with its recommended model built in the `model` schema."""
    con = duckdb.connect()
    tables = build_dataset(1, "S", "sap", SynthSettings()).output_tables()
    for name, data in tables.items():
        load_arrow(con, name, data)
    profile = profile_project(con, {n: n for n in tables}, ProfilingSettings())
    proposals = [
        {**to_proposal(c, None, AgentSettings()).model_dump(by_alias=True), "status": "approved"}
        for c in score_candidates(profile, JoinSettings())
        if c.accepted
    ]
    specs = plan_views(proposals, profile, REQUIREMENT, KPI)
    create_views(con, specs)
    yield con, profile, specs
    con.close()
