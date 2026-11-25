"""The one interface every model call goes through (LLM rules, D-005).

Callers ask for structured output by passing a Pydantic model. Implementations
return a validated instance plus usage numbers; tests use FakeProvider and never
touch the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel


@dataclass(frozen=True)
class Prompt:
    """A rendered prompt: a stable purpose (for logs and fakes), system and user text."""

    purpose: str
    system: str
    user: str


@dataclass(frozen=True)
class Usage:
    """Tokens, latency and estimated cost of one call."""

    provider: str
    model: str
    purpose: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    attempts: int = 1
    cached: bool = False
    error: str | None = None


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    """A validated answer and the usage of the call that produced it."""

    value: T
    usage: Usage


class LLMProvider(Protocol):
    """Structured generation: return an instance of `schema` for `prompt`."""

    name: str
    model: str

    def generate[T: BaseModel](self, prompt: Prompt, schema: type[T]) -> LLMResult[T]:
        """Return a validated instance of `schema` answering `prompt`."""
        ...
