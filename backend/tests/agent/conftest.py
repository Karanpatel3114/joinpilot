import pytest

from joinpilot.agent.graph import AgentContext
from joinpilot.config import Settings
from joinpilot.llm.fake import FakeProvider
from joinpilot.profiling.models import ProjectProfile


@pytest.fixture
def fake_llm() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def ctx(sap_profile: ProjectProfile, fake_llm: FakeProvider) -> AgentContext:
    return AgentContext(
        load_profile=lambda: sap_profile, llm=fake_llm, settings=Settings(_env_file=None)
    )
