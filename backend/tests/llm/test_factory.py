import pytest
from pydantic import BaseModel, SecretStr

from joinpilot.config import LLMSettings, Settings
from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.factory import UnavailableProvider, make_base_provider
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.gemini import GeminiProvider
from joinpilot.llm.provider import Prompt


class Answer(BaseModel):
    value: int


def test_without_a_key_the_model_is_reported_unavailable() -> None:
    provider = make_base_provider(Settings(_env_file=None, gemini_api_key=SecretStr("")))
    assert isinstance(provider, UnavailableProvider)
    with pytest.raises(LLMUnavailableError, match="GEMINI_API_KEY"):
        provider.generate(Prompt("p", "s", "u"), Answer)


def test_fake_and_gemini_providers_are_selected_by_config() -> None:
    fake = make_base_provider(Settings(_env_file=None, llm=LLMSettings(provider="fake")))
    assert isinstance(fake, FakeProvider)
    real = make_base_provider(Settings(_env_file=None, gemini_api_key=SecretStr("k")))
    assert isinstance(real, GeminiProvider)
    assert real.model == "gemini-flash-lite-latest"


def test_the_key_never_appears_in_settings_output() -> None:
    settings = Settings(_env_file=None, gemini_api_key=SecretStr("super-secret"))
    assert "super-secret" not in repr(settings)
    assert "super-secret" not in settings.model_dump_json()
