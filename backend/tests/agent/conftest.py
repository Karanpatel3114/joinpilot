from collections.abc import Iterator
from contextlib import nullcontext

import duckdb
import pytest

from joinpilot.agent.graph import AgentContext
from joinpilot.config import KPISettings, Settings, SynthSettings
from joinpilot.llm.fake import FakeProvider
from joinpilot.profiling.loader import load_arrow
from joinpilot.profiling.models import ProjectProfile
from joinpilot.synth.dataset import build_dataset


@pytest.fixture(scope="module")
def sample_warehouse() -> Iterator[duckdb.DuckDBPyConnection]:
    con = duckdb.connect()
    for name, data in build_dataset(1, "S", "sap", SynthSettings()).output_tables().items():
        load_arrow(con, name, data)
    yield con
    con.close()


@pytest.fixture
def fake_llm() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def ctx(
    sap_profile: ProjectProfile, fake_llm: FakeProvider, sample_warehouse: duckdb.DuckDBPyConnection
) -> AgentContext:
    from datetime import date

    settings = Settings(_env_file=None, kpi=KPISettings(reference_date=date(2026, 6, 30)))
    return AgentContext(
        load_profile=lambda: sap_profile,
        llm=fake_llm,
        settings=settings,
        warehouse=lambda: nullcontext(sample_warehouse),
    )
