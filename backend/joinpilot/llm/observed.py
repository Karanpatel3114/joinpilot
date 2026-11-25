"""Every model call is wrapped here: cache, retries with backoff, validation retry,
and a usage log with tokens, latency and estimated cost (LLM rules)."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from pydantic import BaseModel, ValidationError

from joinpilot.config import LLMSettings
from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.provider import LLMProvider, LLMResult, Prompt, Usage

logger = logging.getLogger(__name__)
RETRYABLE_STATUS = {None, 408, 429, 500, 502, 503, 504}


class UsageLog:
    """In-memory record of calls; runs and evaluation read their totals from it."""

    def __init__(self) -> None:
        self.records: list[Usage] = []

    def add(self, usage: Usage) -> None:
        """Record one call and log its numbers (never its content)."""
        self.records.append(usage)
        logger.info(
            "llm call purpose=%s model=%s in=%d out=%d latency_ms=%.0f attempts=%d cached=%s",
            usage.purpose,
            usage.model,
            usage.input_tokens,
            usage.output_tokens,
            usage.latency_ms,
            usage.attempts,
            usage.cached,
        )

    def totals(self) -> dict[str, float | int]:
        """Summed tokens, latency, cost and call count."""
        return {
            "calls": len(self.records),
            "input_tokens": sum(u.input_tokens for u in self.records),
            "output_tokens": sum(u.output_tokens for u in self.records),
            "latency_ms": round(sum(u.latency_ms for u in self.records), 1),
            "cost_usd": round(sum(u.cost_usd for u in self.records), 6),
        }


class ResponseCache:
    """Validated answers on disk, keyed by model, prompt and schema, to save free-tier quota."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def key(self, model: str, prompt: Prompt, schema: type[BaseModel]) -> str:
        """A stable hash of everything that could change the answer."""
        material = json.dumps(
            [model, prompt.purpose, prompt.system, prompt.user, schema.model_json_schema()],
            sort_keys=True,
        )
        return hashlib.sha256(material.encode()).hexdigest()

    def get(self, key: str) -> str | None:
        """The cached JSON answer, if present."""
        path = self.folder / f"{key}.json"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def put(self, key: str, value_json: str) -> None:
        """Store a validated JSON answer."""
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{key}.json").write_text(value_json, encoding="utf-8")


def estimate_cost(usage: Usage, settings: LLMSettings) -> float:
    """Cost at the model's paid list price (USD per million tokens); free-tier calls cost $0."""
    price = settings.prices_per_million.get(usage.model)
    if not price:
        return 0.0
    return round(usage.input_tokens * price[0] / 1e6 + usage.output_tokens * price[1] / 1e6, 6)


class ObservedProvider:
    """Wrap a provider with caching, retries, one validation retry and usage logging."""

    def __init__(
        self,
        inner: LLMProvider,
        settings: LLMSettings,
        log: UsageLog | None = None,
        cache: ResponseCache | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.inner = inner
        self.name = inner.name
        self.model = inner.model
        self.settings = settings
        self.log = log or UsageLog()
        self.cache = cache
        self.sleep = sleep

    def generate[T: BaseModel](self, prompt: Prompt, schema: type[T]) -> LLMResult[T]:
        """Return a validated answer, from the cache or the model."""
        key = self.cache.key(self.model, prompt, schema) if self.cache else ""
        cached = self.cache.get(key) if self.cache else None
        if cached is not None:
            usage = Usage(provider=self.name, model=self.model, purpose=prompt.purpose, cached=True)
            self.log.add(usage)
            return LLMResult(value=schema.model_validate_json(cached), usage=usage)
        result = self._call_with_retries(prompt, schema)
        if self.cache:
            self.cache.put(key, result.value.model_dump_json())
        return result

    def _call_with_retries[T: BaseModel](self, prompt: Prompt, schema: type[T]) -> LLMResult[T]:
        attempts, fixed_once, current = 0, False, prompt
        while True:
            attempts += 1
            try:
                result = self.inner.generate(current, schema)
                break
            except ValidationError as error:
                if fixed_once:
                    raise LLMUnavailableError(
                        "The language model returned invalid output twice.",
                        {"reason_code": "INVALID_OUTPUT", "purpose": prompt.purpose},
                    ) from error
                fixed_once = True
                current = replace(
                    prompt,
                    user=f"{prompt.user}\n\nYour previous reply did not match the schema: "
                    f"{error.errors(include_url=False)[:3]}. Reply again with valid JSON only.",
                )
            except LLMUnavailableError as error:
                status = error.details.get("status")
                if status not in RETRYABLE_STATUS or attempts > self.settings.max_retries:
                    raise
                delay = min(
                    self.settings.backoff_base_seconds * 2 ** (attempts - 1),
                    self.settings.backoff_max_seconds,
                )
                logger.warning("llm call failed (status %s); retrying in %.1fs", status, delay)
                self.sleep(delay)
        usage = replace(result.usage, attempts=attempts)
        usage = replace(usage, cost_usd=estimate_cost(usage, self.settings))
        self.log.add(usage)
        return LLMResult(value=result.value, usage=usage)
