"""SQL safety: the share of red-team attacks the guard blocks, and of harmless queries it allows."""

from __future__ import annotations

import json
from typing import Any

from joinpilot.config import REPO_ROOT
from joinpilot.sqlgen.guard import Catalog, UnsafeSQLError, guard_sql

ATTACKS = REPO_ROOT / "eval" / "redteam" / "sql_attacks.jsonl"
HARMLESS = REPO_ROOT / "eval" / "redteam" / "harmless.jsonl"


def catalog() -> Catalog:
    """The small catalog the red-team cases are written against."""
    c = Catalog()
    c.add("main", "KNA1", {"KUNNR": "VARCHAR", "NAME1": "VARCHAR", "LAND1": "VARCHAR"})
    c.add("main", "BSID", {"KUNNR": "VARCHAR", "DMBTR": "DECIMAL(15,2)", "ZFBDT": "DATE"})
    c.add(
        "model", "v_bsid", {"KUNNR": "VARCHAR", "DMBTR": "DECIMAL(15,2)", "aging_bucket": "VARCHAR"}
    )
    return c


def blocked(sql: str, mode: str) -> bool:
    """True when the guard refuses the statement."""
    try:
        guard_sql(sql, catalog(), mode)  # type: ignore[arg-type]
    except UnsafeSQLError:
        return True
    return False


def evaluate_redteam() -> dict[str, Any]:
    """Block rate on attacks (target 100%) and wrong-block rate on harmless queries."""
    attacks = [json.loads(line) for line in ATTACKS.read_text().splitlines() if line.strip()]
    harmless = [json.loads(line) for line in HARMLESS.read_text().splitlines() if line.strip()]
    missed = [a["id"] for a in attacks if not blocked(a["sql"], a["mode"])]
    wrongly = [h["id"] for h in harmless if blocked(h["sql"], "select")]
    # Questions use the stricter mode; report what it costs on ordinary queries.
    wrongly_questions = [h["id"] for h in harmless if blocked(h["sql"], "question")]
    return {
        "attacks": len(attacks),
        "block_rate": round(1 - len(missed) / len(attacks), 4),
        "missed": missed,
        "harmless": len(harmless),
        "false_block_rate": round(len(wrongly) / len(harmless), 4),
        "wrongly_blocked": wrongly,
        "false_block_rate_questions": round(len(wrongly_questions) / len(harmless), 4),
        "wrongly_blocked_questions": wrongly_questions,
    }
