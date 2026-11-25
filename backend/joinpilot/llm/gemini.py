"""Google Gemini through the official `google-genai` SDK (free tier, no billing needed).

Structured output: the JSON schema of the requested Pydantic model is sent as the
response schema, and the reply is validated with that model. Models without native
JSON mode (for example Gemma) get the schema in the prompt instead.
"""

from __future__ import annotations

import json
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from joinpilot.config import LLMSettings
from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.provider import LLMResult, Prompt, Usage

JSON_INSTRUCTION = (
    "Reply with one JSON object only, no prose and no code fences, matching this JSON schema:\n"
)


class GeminiProvider:
    """One model on the Gemini API."""

    name = "gemini"

    def __init__(self, settings: LLMSettings, api_key: str) -> None:
        if not api_key:
            raise LLMUnavailableError("GEMINI_API_KEY is not set.")
        self.settings = settings
        self.model = settings.model
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(settings.timeout_seconds * 1000)),
        )

    def native_json(self) -> bool:
        """Gemma models on the Gemini API do not take a response schema."""
        return not self.model.startswith("gemma")

    def generate[T: BaseModel](self, prompt: Prompt, schema: type[T]) -> LLMResult[T]:
        """Ask the model for an instance of `schema`; raise LLMUnavailableError on API errors."""
        system, user = prompt.system, prompt.user
        config = types.GenerateContentConfig(temperature=self.settings.temperature)
        if self.native_json():
            config.system_instruction = system
            config.response_mime_type = "application/json"
            config.response_json_schema = schema.model_json_schema()
        else:
            schema_text = json.dumps(schema.model_json_schema())
            user = f"{system}\n\n{JSON_INSTRUCTION}{schema_text}\n\n{user}"
        started = time.perf_counter()
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=user, config=config
            )
        except genai_errors.APIError as error:
            raise LLMUnavailableError(
                "The language model is unavailable.", {"status": error.code}
            ) from error
        latency = (time.perf_counter() - started) * 1000
        text = (response.text or "").strip().removeprefix("```json").removesuffix("```").strip()
        value = schema.model_validate_json(text)
        meta = response.usage_metadata
        usage = Usage(
            provider=self.name,
            model=self.model,
            purpose=prompt.purpose,
            input_tokens=(meta.prompt_token_count or 0) if meta else 0,
            output_tokens=(meta.candidates_token_count or 0) if meta else 0,
            latency_ms=round(latency, 1),
        )
        return LLMResult(value=value, usage=usage)
