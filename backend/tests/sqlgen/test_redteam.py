"""Every attack in eval/redteam/sql_attacks.jsonl must be blocked by the guard."""

import json
from typing import Any

import pytest

from joinpilot.config import REPO_ROOT
from joinpilot.sqlgen.guard import Catalog, UnsafeSQLError, guard_sql

ATTACKS: list[dict[str, Any]] = [
    json.loads(line)
    for line in (REPO_ROOT / "eval" / "redteam" / "sql_attacks.jsonl").read_text().splitlines()
    if line.strip()
]
HARMLESS = [
    "SELECT COUNT(*) FROM KNA1",
    "SELECT LAND1, COUNT(*) AS customers FROM KNA1 GROUP BY LAND1 ORDER BY customers DESC",
    "SELECT k.NAME1, SUM(b.DMBTR) FROM BSID b JOIN KNA1 k ON lpad(b.KUNNR, 10, '0') = k.KUNNR "
    "GROUP BY 1 ORDER BY 2 DESC LIMIT 5",
    "WITH totals AS (SELECT KUNNR, SUM(DMBTR) AS t FROM BSID GROUP BY 1) SELECT AVG(t) FROM totals",
    "SELECT * FROM model.v_bsid WHERE aging_bucket = '90+'",
    "SELECT strftime(ZFBDT, '%Y-%m') AS month, COUNT(*) FROM BSID GROUP BY 1",
    "SELECT NAME1 FROM KNA1 WHERE NAME1 LIKE '%Supply%' AND LAND1 IN ('DE', 'FR')",
    "SELECT KUNNR, RANK() OVER (ORDER BY KUNNR) FROM KNA1",
]


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    c = Catalog()
    c.add("main", "KNA1", {"KUNNR": "VARCHAR", "NAME1": "VARCHAR", "LAND1": "VARCHAR"})
    c.add("main", "BSID", {"KUNNR": "VARCHAR", "DMBTR": "DECIMAL(15,2)", "ZFBDT": "DATE"})
    c.add(
        "model", "v_bsid", {"KUNNR": "VARCHAR", "DMBTR": "DECIMAL(15,2)", "aging_bucket": "VARCHAR"}
    )
    return c


def test_the_attack_set_is_large_and_varied() -> None:
    assert len(ATTACKS) >= 50
    assert len({a["category"] for a in ATTACKS}) >= 10
    assert len({a["id"] for a in ATTACKS}) == len(ATTACKS)


@pytest.mark.parametrize("attack", ATTACKS, ids=[a["id"] for a in ATTACKS])
def test_every_attack_is_blocked(attack: dict[str, Any], catalog: Catalog) -> None:
    with pytest.raises(UnsafeSQLError):
        guard_sql(attack["sql"], catalog, attack["mode"])


@pytest.mark.parametrize("sql", HARMLESS)
def test_ordinary_questions_are_not_blocked(sql: str, catalog: Catalog) -> None:
    guard_sql(sql, catalog)
