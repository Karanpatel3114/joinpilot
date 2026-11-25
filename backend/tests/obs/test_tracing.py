import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, SecretStr

from joinpilot.config import LLMSettings, Settings
from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.observed import ObservedProvider
from joinpilot.llm.provider import Prompt
from joinpilot.obs.tracing import LangfuseTracer, NoopTracer, make_tracer

PROMPT = Prompt(purpose="demo", system="secret example values", user="u")


class Answer(BaseModel):
    value: int


class StubLangfuse:
    """Records what would be sent to Langfuse."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.observations: list[dict[str, Any]] = []

    def start_observation(self, **kwargs: Any) -> Any:
        self.observations.append(kwargs)
        return SimpleNamespace(end=lambda: None)


def keyed(**extra: Any) -> Settings:
    return Settings(
        _env_file=None,
        langfuse_public_key=SecretStr("pk"),
        langfuse_secret_key=SecretStr("sk"),
        **extra,
    )


def test_tracing_is_off_without_keys() -> None:
    assert isinstance(make_tracer(Settings(_env_file=None)), NoopTracer)


def test_keys_enable_langfuse_with_metadata_only(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("langfuse")
    module.Langfuse = StubLangfuse  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", module)
    tracer = make_tracer(keyed())
    assert isinstance(tracer, LangfuseTracer)
    llm = ObservedProvider(
        FakeProvider({"demo": lambda p: {"value": 1}}), LLMSettings(), tracer=tracer
    )
    llm.generate(PROMPT, Answer)
    [sent] = tracer.client.observations
    assert sent["name"] == "llm.demo" and sent["as_type"] == "generation"
    assert sent["input"] is None and sent["output"] is None
    assert "secret example values" not in str(sent)


def test_failures_are_traced_as_errors_and_text_only_when_enabled() -> None:
    client = StubLangfuse()
    llm = ObservedProvider(
        FakeProvider(), LLMSettings(), tracer=LangfuseTracer(client, capture_prompts=True)
    )
    with pytest.raises(LLMUnavailableError):
        llm.generate(PROMPT, Answer)
    [sent] = client.observations
    assert sent["level"] == "ERROR"
    assert sent["input"]["system"] == "secret example values"


def test_missing_extra_falls_back_to_no_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "langfuse", None)
    assert isinstance(make_tracer(keyed()), NoopTracer)
