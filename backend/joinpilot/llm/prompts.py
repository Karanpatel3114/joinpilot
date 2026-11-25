"""Versioned prompt files (`agent/prompts/<name>.<version>.md`), never inline strings.

A prompt file has a `## System` and a `## User` section. A snippet file (text the
code appends to a prompt, such as a correction request) has no sections.
`$placeholders` are filled with `string.Template`, so JSON braces need no escaping.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template

from joinpilot.llm.provider import Prompt

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "agent" / "prompts"


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


def read(name: str, version: str) -> str:
    """The text of `prompts/<name>.<version>.md`."""
    return (PROMPTS_DIR / f"{name}.{version}.md").read_text(encoding="utf-8")


def load_prompt(name: str, version: str = "v1") -> PromptTemplate:
    """Read a prompt file and split it into system and user parts."""
    system_part, user_part = read(name, version).split("## User", 1)
    system = system_part.replace("## System", "", 1).strip()
    return PromptTemplate(name, version, system, user_part.strip())


def snippet(name: str, version: str = "v1", **values: str) -> str:
    """A filled-in snippet file, for text appended to a prompt."""
    return Template(read(name, version).strip()).substitute(values)
