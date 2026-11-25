"""Fixtures shared across test packages."""

import duckdb
import pytest

from joinpilot.config import ProfilingSettings, SynthSettings
from joinpilot.profiling.loader import load_arrow
from joinpilot.profiling.models import ProjectProfile
from joinpilot.profiling.service import profile_project
from joinpilot.synth.dataset import build_dataset
from joinpilot.synth.naming import Naming


def erp_profile(seed: int, naming: Naming) -> ProjectProfile:
    """Profile a small synthetic ERP dataset in memory, as a project would."""
    con = duckdb.connect()
    tables = build_dataset(seed, "S", naming, SynthSettings()).output_tables()
    for name, data in tables.items():
        load_arrow(con, name, data)
    profile = profile_project(con, {name: name for name in tables}, ProfilingSettings())
    con.close()
    return profile


@pytest.fixture(scope="session")
def sap_profile() -> ProjectProfile:
    return erp_profile(1, "sap")


@pytest.fixture(scope="session")
def friendly_profile() -> ProjectProfile:
    return erp_profile(1, "friendly")
