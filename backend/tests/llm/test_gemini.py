"""The Gemini provider against a stand-in SDK client: no network, no key needed."""

from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors as genai_errors
from pydantic import BaseModel

import joinpilot.llm.gemini as gemini
from joinpilot.config import LLMSettings
from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.provider import Prompt


class Answer(BaseModel):
    value: int


class StubModels:
    def __init__(self, reply: Any) -> None:
        self.reply = reply
        self.requests: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def provider(monkeypatch: pytest.MonkeyPatch, reply: Any, model: str = "gemini-x") -> Any:
    models = StubModels(reply)
    monkeypatch.setattr(gemini.genai, "Client", lambda **kwargs: SimpleNamespace(models=models))
    return gemini.GeminiProvider(LLMSettings(model=model), api_key="test-key"), models


def reply(text: str) -> Any:
    usage = SimpleNamespace(prompt_token_count=12, candidates_token_count=4)
    return SimpleNamespace(text=text, usage_metadata=usage)


PROMPT = Prompt(purpose="demo", system="Answer in JSON.", user="Seven?")


def test_native_json_mode_sends_the_schema_and_validates_the_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gem, models = provider(monkeypatch, reply('{"value": 7}'))
    result = gem.generate(PROMPT, Answer)
    assert result.value == Answer(value=7)
    assert (result.usage.input_tokens, result.usage.output_tokens) == (12, 4)
    config = models.requests[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == Answer.model_json_schema()
    assert config.system_instruction == "Answer in JSON."


def test_gemma_models_get_the_schema_in_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    gem, models = provider(monkeypatch, reply('```json\n{"value": 1}\n```'), model="gemma-4")
    assert gem.generate(PROMPT, Answer).value == Answer(value=1)
    assert "JSON schema" in models.requests[0]["contents"]
    assert models.requests[0]["config"].response_mime_type is None


def test_api_errors_become_llm_unavailable_with_the_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = genai_errors.ClientError(429, {"error": {"code": 429, "message": "quota"}})
    gem, _ = provider(monkeypatch, error)
    with pytest.raises(LLMUnavailableError) as raised:
        gem.generate(PROMPT, Answer)
    assert raised.value.details["status"] == 429


def test_a_missing_key_is_refused() -> None:
    with pytest.raises(LLMUnavailableError):
        gemini.GeminiProvider(LLMSettings(), api_key="")


def test_network_timeouts_are_reported_as_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    gem, _ = provider(monkeypatch, httpx.ConnectTimeout("slow"))
    with pytest.raises(LLMUnavailableError) as raised:
        gem.generate(PROMPT, Answer)
    assert raised.value.details["status"] == 408
