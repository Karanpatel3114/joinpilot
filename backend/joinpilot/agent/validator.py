"""Evidence validator: an explanation may only cite this join's evidence, and every
number or uniqueness claim it makes must agree with that evidence (D-002).

Numbers are tied to what they describe: "X% unique" must match a uniqueness value,
"X% of ... values" an inclusion or coverage value. Percentages written in words
cannot be checked, so they are rejected.
"""

from __future__ import annotations

import re

from joinpilot.joins.models import JoinCandidate

EVIDENCE_ID = re.compile(r"\b(?:ov|uk)_\d{3,}\b", re.IGNORECASE)
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|per\s?cent\b)", re.IGNORECASE)
RATIO = re.compile(r"(?<![\d.])(0?\.\d{2,})(?![\d%])")
NUMBER_WORDS = (
    "zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    "fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|"
    "eighty|ninety|hundred"
)
WORDED_PERCENT = re.compile(rf"\b(?:{NUMBER_WORDS})\b[\w\s-]{{0,30}}?\bper\s?cent\b", re.I)
UNIQUE_WORDS = re.compile(r"\bunique(?:ly)?\b|\bprimary key\b", re.IGNORECASE)
LIMITING = re.compile(
    r"\bnot\b|\bnon-?unique\b|\bonly\b|\bneither\b|\bnever\b|n't\b|%|\bper\s?cent\b",
    re.IGNORECASE,
)
CLAUSE_BREAK = re.compile(r"[;,]|\band\b|\bbut\b|(?<=[.!?])\s+", re.IGNORECASE)


def kind_of_number(text_after: str) -> str:
    """What a stated percentage describes, judged from the words right after it."""
    following = text_after.lower().lstrip()
    if following.startswith("unique"):
        return "uniqueness"
    if following.startswith("of "):
        return "overlap"
    return "any"


def allowed_numbers(c: JoinCandidate) -> dict[str, list[float]]:
    """Evidence values as percentages, grouped by what they describe."""
    uniqueness = [c.target_uniqueness * 100, c.source_uniqueness * 100]
    overlap = [c.inclusion_ratio * 100, c.coverage_ratio * 100]
    return {
        "uniqueness": uniqueness,
        "overlap": overlap,
        "any": [*uniqueness, *overlap, c.score * 100],
    }


def number_problems(c: JoinCandidate, text: str, tolerance: float) -> list[str]:
    """Every stated percentage or ratio must match evidence of the same kind."""
    allowed = allowed_numbers(c)
    stated = [(float(m.group(1)), m.group(0), text[m.end() :]) for m in PERCENT.finditer(text)]
    stated += [(float(m.group(1)) * 100, m.group(0), text[m.end() :]) for m in RATIO.finditer(text)]
    problems = []
    for value, shown, after in stated:
        kind = kind_of_number(after)
        if not any(abs(value - known) <= tolerance for known in allowed[kind]):
            what = {"uniqueness": "uniqueness", "overlap": "overlap", "any": "evidence"}[kind]
            problems.append(f"states {shown.strip()}, which matches no {what} number")
    if WORDED_PERCENT.search(text):
        problems.append("states a percentage in words; use the evidence number in digits")
    return problems


def mentions(clause: str, qualified: str, other: str) -> bool:
    """True if the clause names this column (bare names only when the sides differ)."""
    bare, other_bare = qualified.split(".", 1)[1], other.split(".", 1)[1]
    if qualified.lower() in clause.lower():
        return True
    return bare != other_bare and re.search(rf"\b{re.escape(bare)}\b", clause, re.I) is not None


def uniqueness_problems(c: JoinCandidate, text: str, unique_min: float) -> list[str]:
    """A plain claim that a column is unique must be true for that column.

    Clauses that limit the claim ("not", "only", a percentage) are judged by the
    number check instead. A claim that names neither column is read as being about
    the target, the side a join needs to be unique.
    """
    problems = []
    for clause in CLAUSE_BREAK.split(text):
        if not clause or not UNIQUE_WORDS.search(clause) or LIMITING.search(clause):
            continue
        sides = [(c.to, c.from_, c.target_uniqueness), (c.from_, c.to, c.source_uniqueness)]
        named = [(col, u) for col, other, u in sides if mentions(clause, col, other)]
        for column, uniqueness in named or [(c.to, c.target_uniqueness)]:
            if uniqueness < unique_min:
                problems.append(f"claims {column} is unique, but it is {uniqueness:.1%} unique")
    return problems


def check_explanation(
    candidate: JoinCandidate,
    explanation: str,
    cited_ids: list[str],
    unique_min: float,
    tolerance_points: float,
) -> list[str]:
    """Return the problems with one explanation; an empty list means it is grounded."""
    if not explanation.strip():
        return ["the explanation is empty"]
    allowed = {e.lower() for e in candidate.evidence_ids}
    in_text = {m.lower() for m in EVIDENCE_ID.findall(explanation)}
    cited = in_text | {e.lower() for e in cited_ids}
    problems = [
        f"cites {e}, which is not evidence for {candidate.edge_id}" for e in sorted(cited - allowed)
    ]
    if not in_text & allowed:
        problems.append("cites none of its evidence ids in the explanation text")
    problems += number_problems(candidate, explanation, tolerance_points)
    problems += uniqueness_problems(candidate, explanation, unique_min)
    return problems
