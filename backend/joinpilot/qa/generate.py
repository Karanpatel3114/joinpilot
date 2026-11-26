"""Turn a question into guarded SQL over the semantic model.

The model drafts one query from the views' columns, their meanings and the
dashboard's tested queries. The guard checks it against the model views only; when
it refuses, the model gets the reason and one more try (QA__MAX_ATTEMPTS). SQL that
never passes is not run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from joinpilot.llm.prompts import load_prompt, snippet
from joinpilot.llm.provider import LLMProvider, Prompt
from joinpilot.sqlgen.guard import Catalog, UnsafeSQLError, guard_sql

Chart = Literal["number", "line", "bar", "table"]


class SQLDraft(BaseModel):
    """What the model returns for a question."""

    sql: str = Field(min_length=1, max_length=8000)
    chart: Chart
    explanation: str = Field(max_length=600)


@dataclass(frozen=True)
class Drafted:
    """A query that passed the guard, how to show it, and how many tries it took."""

    sql: str
    chart: Chart
    explanation: str
    attempts: int


def draft_sql(
    question: str,
    model: str,
    examples: str,
    llm: LLMProvider,
    catalog: Catalog,
    max_attempts: int,
) -> Drafted:
    """Ask for SQL and guard it; raise the guard's last refusal if no draft passes."""
    prompt = load_prompt("qa_sql").render(
        question=question.strip(), model=model, examples=examples or "(none yet)"
    )
    refusal: UnsafeSQLError | None = None
    for attempt in range(1, max_attempts + 1):
        draft = llm.generate(prompt, SQLDraft).value
        try:
            sql = guard_sql(draft.sql, catalog)
        except UnsafeSQLError as error:
            refusal = error
            correction = snippet("fix_sql", error=error.message, sql=draft.sql)
            prompt = Prompt(prompt.purpose, prompt.system, f"{prompt.user}\n\n{correction}")
            continue
        return Drafted(sql, draft.chart, draft.explanation, attempt)
    if refusal is None:
        raise ValueError("max_attempts must be at least 1")
    raise refusal
