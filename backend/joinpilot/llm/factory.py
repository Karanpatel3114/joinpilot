"""Build the configured provider, or one that reports the model as unavailable."""

from __future__ import annotations

from pydantic import BaseModel

from joinpilot.config import Settings
from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.provider import LLMProvider, LLMResult, Prompt


class UnavailableProvider:
    """Stands in when no model is configured; every call raises LLMUnavailableError.

    Agent steps catch that error and fall back to deterministic behavior, so the
    app keeps working without a key or after the free quota runs out.
    """

    name = "unavailable"

    def __init__(self, reason: str) -> None:
        self.model = "none"
        self.reason = reason

    def generate[T: BaseModel](self, prompt: Prompt, schema: type[T]) -> LLMResult[T]:
        """Always refuse, with the reason."""
        raise LLMUnavailableError(self.reason, {"reason_code": "LLM_UNAVAILABLE"})


def make_base_provider(settings: Settings) -> LLMProvider:
    """The raw provider for the configured backend."""
    if settings.llm.provider == "fake":
        return FakeProvider()
    key = settings.gemini_api_key.get_secret_value()
    if not key:
        return UnavailableProvider("GEMINI_API_KEY is not set, so the language model is off.")
    from joinpilot.llm.gemini import GeminiProvider

    return GeminiProvider(settings.llm, key)
