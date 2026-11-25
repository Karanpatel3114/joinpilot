"""Versioned prompt files (`prompts/<name>.<version>.md`), never inline strings.

Each file has a `## System` and a `## User` section; `$placeholders` in them are
filled with `string.Template`, so JSON braces in prompts need no escaping.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template

from joinpilot.llm.provider import Prompt

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class PromptTemplate:
    """One versioned prompt with its system and user parts."""

    name: str
    version: str
    system: str
    user: str

    def render(self, **values: str) -> Prompt:
        """Fill the placeholders; a missing value raises KeyError."""
        return Prompt(
            purpose=self.name,
            system=Template(self.system).substitute(values),
            user=Template(self.user).substitute(values),
        )


def load_prompt(name: str, version: str = "v1") -> PromptTemplate:
    """Read `prompts/<name>.<version>.md` and split it into system and user parts."""
    text = (PROMPTS_DIR / f"{name}.{version}.md").read_text(encoding="utf-8")
    system_part, user_part = text.split("## User", 1)
    system = system_part.replace("## System", "", 1).strip()
    return PromptTemplate(name, version, system, user_part.strip())
