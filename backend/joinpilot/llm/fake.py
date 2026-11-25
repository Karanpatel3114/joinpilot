"""An offline provider for tests: answers come from handlers registered per purpose."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.provider import LLMResult, Prompt, Usage

Handler = Callable[[Prompt], BaseModel | dict[str, Any] | str]


class FakeProvider:
    """Deterministic stand-in for a real model.

    Register a handler per prompt purpose that returns a model instance, a dict or a
    JSON string. Every call is recorded in `calls`, so tests can assert on prompts.
    """

    name = "fake"

    def __init__(self, handlers: dict[str, Handler] | None = None, model: str = "fake-1") -> None:
        self.model = model
        self.handlers: dict[str, Handler] = dict(handlers or {})
        self.calls: list[Prompt] = []

    def on(self, purpose: str, handler: Handler) -> FakeProvider:
        """Register (or replace) the handler for one purpose; returns self for chaining."""
        self.handlers[purpose] = handler
        return self

    def generate[T: BaseModel](self, prompt: Prompt, schema: type[T]) -> LLMResult[T]:
        """Answer from the handler registered for the prompt's purpose."""
        self.calls.append(prompt)
        handler = self.handlers.get(prompt.purpose)
        if handler is None:
            raise LLMUnavailableError(f"FakeProvider has no handler for '{prompt.purpose}'.")
        raw = handler(prompt)
        if isinstance(raw, str):
            value = schema.model_validate_json(raw)
        elif isinstance(raw, BaseModel):
            value = schema.model_validate(raw.model_dump())
        else:
            value = schema.model_validate(raw)
        usage = Usage(
            provider=self.name,
            model=self.model,
            purpose=prompt.purpose,
            input_tokens=len(prompt.system.split()) + len(prompt.user.split()),
            output_tokens=len(value.model_dump_json().split()),
        )
        return LLMResult(value=value, usage=usage)
