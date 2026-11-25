"""Requirement parsing: from plain English to entities, measures, dimensions and filters.

The model sees only table and column names, types and two example values per
column. Its answer is validated: tables it names must exist. Without a model, a
keyword parser gives a usable (if rougher) result.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from joinpilot.errors import LLMUnavailableError
from joinpilot.llm.prompts import load_prompt
from joinpilot.llm.provider import LLMProvider
from joinpilot.profiling.models import ProjectProfile

EXAMPLE_VALUES = 2
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
ENTITY_WORDS = {
    "customer": ("customer", "client", "debtor"),
    "product": ("product", "material", "item"),
    "sales order": ("order", "sales", "revenue"),
    "receivable": ("receivable", "open item", "overdue", "aging", "ageing", "invoice"),
}
MEASURE_WORDS = {
    "revenue": (("revenue", "sales value", "net value"), "sum of item net value"),
    "open amount": (
        ("receivable", "open item", "overdue", "outstanding"),
        "sum of open item amounts",
    ),
    "order count": (
        ("number of orders", "order count", "how many orders"),
        "count of sales orders",
    ),
}
DIMENSION_WORDS = ("aging bucket", "product group", "month", "customer", "country", "sales org")


class Measure(BaseModel):
    """A number to report and how it is computed."""

    name: str
    description: str


class Filter(BaseModel):
    """A condition on the data, such as a year."""

    field: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "between", "in"]
    value: str


class RequirementDraft(BaseModel):
    """What the model returns for a requirement."""

    summary: str
    entities: list[str] = Field(default_factory=list)
    measures: list[Measure] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[Filter] = Field(default_factory=list)
    relevant_tables: list[str] = Field(default_factory=list)


class ParsedRequirement(RequirementDraft):
    """A validated requirement, with where it came from."""

    source: Literal["llm", "fallback"] = "llm"


def describe_tables(profile: ProjectProfile) -> str:
    """One line per table: columns with type and a couple of example values."""
    lines = []
    for table in profile.tables:
        columns = ", ".join(
            f"{c.name} {c.type} {c.sample_values[:EXAMPLE_VALUES]}" for c in table.columns
        )
        lines.append(f"- {table.name} ({table.row_count} rows): {columns}")
    return "\n".join(lines)


def fallback_parse(requirement: str, profile: ProjectProfile) -> ParsedRequirement:
    """Keyword parsing for when no model is available; every table is considered relevant."""
    text = requirement.lower()
    return ParsedRequirement(
        summary=requirement.strip(),
        entities=[e for e, words in ENTITY_WORDS.items() if any(w in text for w in words)],
        measures=[
            Measure(name=name, description=description)
            for name, (words, description) in MEASURE_WORDS.items()
            if any(w in text for w in words)
        ],
        dimensions=[d for d in DIMENSION_WORDS if d in text],
        filters=[Filter(field="year", operator="=", value=y) for y in YEAR.findall(requirement)],
        relevant_tables=[t.name for t in profile.tables],
        source="fallback",
    )


def parse_requirement(
    requirement: str, profile: ProjectProfile, llm: LLMProvider
) -> tuple[ParsedRequirement, list[str]]:
    """Parse with the model, validating table names; fall back to keywords if it is down."""
    prompt = load_prompt("parse_requirement").render(
        requirement=requirement.strip(), tables=describe_tables(profile)
    )
    try:
        draft = llm.generate(prompt, RequirementDraft).value
    except (LLMUnavailableError, ValidationError) as error:
        message = error.message if isinstance(error, LLMUnavailableError) else "invalid output"
        return fallback_parse(requirement, profile), [f"Keyword parsing used: {message}"]
    known = {t.name.casefold(): t.name for t in profile.tables}
    tables = [known[t.casefold()] for t in draft.relevant_tables if t.casefold() in known]
    warnings = [
        f"The model named a table that does not exist and it was ignored: {t}"
        for t in draft.relevant_tables
        if t.casefold() not in known
    ]
    if not tables:
        tables = list(known.values())
        warnings.append("No known tables were named, so every table is considered.")
    parsed = ParsedRequirement(
        **draft.model_dump(exclude={"relevant_tables"}), relevant_tables=tables
    )
    return parsed, warnings
