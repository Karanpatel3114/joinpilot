from pathlib import Path

import pytest
from pydantic import BaseModel

from joinpilot.config import LLMSettings
from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.observed import ObservedProvider, ResponseCache, UsageLog, estimate_cost
from joinpilot.llm.provider import Prompt, Usage

PROMPT = Prompt(purpose="demo", system="s", user="u")


class Answer(BaseModel):
    value: int


def flaky(failures: list[object]) -> FakeProvider:
    """A provider that raises the queued failures first, then answers."""

    def handler(prompt: Prompt) -> dict[str, int]:
        if failures:
            failure = failures.pop(0)
            if isinstance(failure, Exception):
                raise failure
            return failure  # type: ignore[return-value]
        return {"value": 1}

    return FakeProvider({"demo": handler})


def observed(inner: FakeProvider, **kwargs: object) -> tuple[ObservedProvider, list[float]]:
    sleeps: list[float] = []
    wrapper = ObservedProvider(inner, LLMSettings(**kwargs), sleep=sleeps.append)  # type: ignore[arg-type]
    return wrapper, sleeps


def test_rate_limits_are_retried_with_exponential_backoff() -> None:
    errors = [LLMUnavailableError("busy", {"status": 429}) for _ in range(2)]
    wrapper, sleeps = observed(flaky(list(errors)))
    result = wrapper.generate(PROMPT, Answer)
    assert result.value.value == 1
    assert result.usage.attempts == 3
    assert sleeps == [2.0, 4.0]


def test_non_retryable_errors_and_exhausted_retries_are_raised() -> None:
    wrapper, sleeps = observed(flaky([LLMUnavailableError("bad key", {"status": 403})]))
    with pytest.raises(LLMUnavailableError):
        wrapper.generate(PROMPT, Answer)
    assert sleeps == []
    always_busy = [LLMUnavailableError("busy", {"status": 503}) for _ in range(5)]
    wrapper, sleeps = observed(flaky(always_busy), max_retries=2)
    with pytest.raises(LLMUnavailableError):
        wrapper.generate(PROMPT, Answer)
    assert len(sleeps) == 2


def test_invalid_output_gets_one_corrective_retry_then_fails_cleanly() -> None:
    inner = flaky([{"value": "x"}])
    wrapper, _ = observed(inner)
    assert wrapper.generate(PROMPT, Answer).value.value == 1
    assert "did not match the schema" in inner.calls[1].user
    wrapper, _ = observed(flaky([{"value": "x"}, {"value": "y"}]))
    with pytest.raises(LLMUnavailableError) as error:
        wrapper.generate(PROMPT, Answer)
    assert error.value.details["reason_code"] == "INVALID_OUTPUT"


def test_cached_answers_skip_the_model(tmp_path: Path) -> None:
    inner = flaky([])
    log = UsageLog()
    wrapper = ObservedProvider(inner, LLMSettings(), log=log, cache=ResponseCache(tmp_path))
    first = wrapper.generate(PROMPT, Answer)
    second = wrapper.generate(PROMPT, Answer)
    assert first.value == second.value
    assert len(inner.calls) == 1
    assert [u.cached for u in log.records] == [False, True]
    assert log.totals()["calls"] == 2


def test_cost_uses_configured_list_prices_and_defaults_to_zero() -> None:
    usage = Usage("gemini", "m", "p", input_tokens=1_000_000, output_tokens=500_000)
    assert estimate_cost(usage, LLMSettings()) == 0.0
    priced = LLMSettings(prices_per_million={"m": (0.10, 0.40)})
    assert estimate_cost(usage, priced) == 0.3
