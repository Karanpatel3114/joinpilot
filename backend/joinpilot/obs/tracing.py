"""Optional Langfuse tracing of model calls (install with `uv sync --extra tracing`).

Tracing is on only when both Langfuse keys are set. By default only metadata is
sent (purpose, model, tokens, latency, attempts); prompt and answer text are sent
only if LANGFUSE_CAPTURE_PROMPTS is true, because prompts contain example values.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Protocol

from joinpilot.config import Settings
from joinpilot.llm.provider import Prompt, Usage

logger = logging.getLogger(__name__)


class Tracer(Protocol):
    """Receives one record per model call."""

    def generation(
        self, usage: Usage, prompt: Prompt, output_json: str | None, error: str | None
    ) -> None:
        """Record a finished (or failed) call."""
        ...


class NoopTracer:
    """The default: record nothing."""

    def generation(
        self, usage: Usage, prompt: Prompt, output_json: str | None, error: str | None
    ) -> None:
        """Do nothing."""


class LangfuseTracer:
    """Send each call to Langfuse as a generation observation."""

    def __init__(self, client: Any, capture_prompts: bool) -> None:
        self.client = client
        self.capture_prompts = capture_prompts

    def generation(
        self, usage: Usage, prompt: Prompt, output_json: str | None, error: str | None
    ) -> None:
        """Record tokens, latency and outcome; text only when capture is enabled."""
        observation = self.client.start_observation(
            name=f"llm.{usage.purpose}",
            as_type="generation",
            model=usage.model,
            input={"system": prompt.system, "user": prompt.user} if self.capture_prompts else None,
            output=output_json if self.capture_prompts else None,
            usage_details={"input": usage.input_tokens, "output": usage.output_tokens},
            metadata={
                "latency_ms": usage.latency_ms,
                "attempts": usage.attempts,
                "cached": usage.cached,
            },
            level="ERROR" if error else "DEFAULT",
            status_message=error,
        )
        observation.end()


def make_tracer(settings: Settings) -> Tracer:
    """Langfuse when its keys are set and the extra is installed, otherwise no tracing."""
    public = settings.langfuse_public_key.get_secret_value()
    secret = settings.langfuse_secret_key.get_secret_value()
    if not (public and secret):
        return NoopTracer()
    try:
        langfuse = importlib.import_module("langfuse")
    except ImportError:
        logger.warning("Langfuse keys are set but the 'tracing' extra is not installed")
        return NoopTracer()
    client = langfuse.Langfuse(
        public_key=public, secret_key=secret, base_url=settings.langfuse_host
    )
    return LangfuseTracer(client, settings.langfuse_capture_prompts)
