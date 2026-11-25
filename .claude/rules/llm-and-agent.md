---
paths:
  - "backend/joinpilot/agent/**"
  - "backend/joinpilot/llm/**"
  - "backend/joinpilot/qa/**"
  - "backend/joinpilot/kpi/**"
---
# LLM and agent rules

- Every model call goes through `joinpilot.llm.provider.LLMProvider`. Implementations: Gemini (default, free tier), `FakeProvider` for tests, and optionally Ollama for local runs. No SDK calls anywhere else.
- Ask for structured output and validate it with a Pydantic model. On a validation failure, retry once with the error message, then fail cleanly with a reason code.
- Temperature, model name, timeouts and retry backoff come from config.
- Deterministic first, LLM second. Profiling and join candidates are pure code. The LLM may interpret the requirement, rank and explain candidates, and draft SQL. It may not add a join that profiling did not produce. If it suggests one, mark it `unverified` and compute evidence before showing it.
- Every explanation cites evidence IDs from the profiling results (overlap ratio, uniqueness, cardinality, normalization). The evidence validator rejects explanations that cite unknown IDs or contradict the numbers.
- The LangGraph graph pauses with an interrupt for human approval before any view is created. State is saved with the Postgres checkpointer so a run can resume.
- Prompts live in `backend/joinpilot/agent/prompts/` as versioned files, never inline strings. After changing a prompt, run the `run-eval` skill on the dev split and note the change in docs/decisions.md.
- Log tokens, latency and estimated cost for every call. Send traces to Langfuse only when its keys are set in `.env`.
- Never send secrets, and never send more rows than needed. Send column statistics and at most a few sample values per column.
