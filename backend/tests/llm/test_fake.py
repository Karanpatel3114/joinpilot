import pytest
from pydantic import BaseModel, ValidationError

from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.fake import FakeProvider
from joinpilot.llm.provider import Prompt


class Answer(BaseModel):
    value: int


def prompt(purpose: str = "demo") -> Prompt:
    return Prompt(purpose=purpose, system="Be brief.", user="Give a number.")


@pytest.mark.parametrize("raw", [Answer(value=3), {"value": 3}, '{"value": 3}'])
def test_handlers_may_return_models_dicts_or_json(raw: object) -> None:
    fake = FakeProvider({"demo": lambda p: raw})  # type: ignore[arg-type, return-value]
    result = fake.generate(prompt(), Answer)
    assert result.value == Answer(value=3)
    assert result.usage.provider == "fake" and result.usage.input_tokens > 0
    assert fake.calls == [prompt()]


def test_missing_handler_means_the_model_is_unavailable() -> None:
    with pytest.raises(LLMUnavailableError):
        FakeProvider().generate(prompt("other"), Answer)


def test_invalid_answers_fail_validation() -> None:
    fake = FakeProvider().on("demo", lambda p: {"value": "not a number"})
    with pytest.raises(ValidationError):
        fake.generate(prompt(), Answer)
