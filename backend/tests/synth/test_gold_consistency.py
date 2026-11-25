"""Gold is computed in Python; here DuckDB SQL over the written files must agree exactly."""

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pytest

from joinpilot.config import SynthSettings
from joinpilot.synth.dataset import build_dataset
from joinpilot.synth.generate import write_dataset
from joinpilot.synth.gold import write_gold

SETTINGS = SynthSettings()
DUE = "(ZFBDT + ZBD1T * INTERVAL 1 DAY)"
OVERDUE_DAYS = f"date_diff('day', CAST({DUE} AS DATE), DATE '2026-06-30')"


@pytest.fixture(scope="module")
def env(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Any, Path]]:
    root = tmp_path_factory.mktemp("consistency")
    dataset = build_dataset(2, "S", "sap", SETTINGS)
    write_dataset(dataset, root / "data")
    write_gold(dataset, root / "gold", SETTINGS)
    con = duckdb.connect()
    for table in ("KNA1", "MARA", "MAKT", "VBAK", "VBAP", "BSID"):
        path = (root / "data" / f"{table}.parquet").as_posix()
        con.execute(f"CREATE VIEW {table} AS SELECT * FROM read_parquet('{path}')")
    yield con, root / "gold"
    con.close()


def load(gold: Path, name: str) -> Any:
    return json.loads((gold / name).read_text())


def question(gold: Path, template: str) -> dict[str, Any]:
    lines = (gold / "qa.jsonl").read_text().splitlines()
    return next(q for q in map(json.loads, lines) if q["template"] == template)


def test_aging_buckets_match_sql(env: tuple[Any, Path]) -> None:
    con, gold = env
    rows = con.execute(f"""
        SELECT CASE WHEN d <= 0 THEN 'not_due' WHEN d <= 30 THEN '1-30'
                    WHEN d <= 60 THEN '31-60' WHEN d <= 90 THEN '61-90' ELSE '90+' END,
               SUM(DMBTR)
        FROM (SELECT {OVERDUE_DAYS} AS d, DMBTR FROM BSID) GROUP BY 1
    """).fetchall()
    expected = {b["bucket"]: Decimal(b["amount"]) for b in load(gold, "kpis.json")["aging_buckets"]}
    assert dict(rows) == expected


def test_revenue_by_group_matches_sql_with_left_join(env: tuple[Any, Path]) -> None:
    con, gold = env
    rows = con.execute("""
        SELECT m.MATKL, SUM(p.NETWR) FROM VBAP p
        JOIN VBAK k ON p.VBELN = k.VBELN
        LEFT JOIN MARA m ON p.MATNR = m.MATNR
        WHERE substr(k.ERDAT, 1, 4) = '2026' GROUP BY 1
    """).fetchall()
    expected = {
        r["product_group"]: Decimal(r["revenue"])
        for r in load(gold, "kpis.json")["revenue_2026_by_product_group"]
    }
    assert dict(rows) == expected


def test_top_customers_and_monthly_counts_match_sql(env: tuple[Any, Path]) -> None:
    con, gold = env
    kpis = load(gold, "kpis.json")
    top = con.execute("""
        SELECT KUNNR, SUM(NETWR) AS v FROM VBAK GROUP BY 1 ORDER BY v DESC, KUNNR LIMIT 10
    """).fetchall()
    assert top == [
        (r["customer_id"], Decimal(r["revenue"])) for r in kpis["top_customers_by_revenue"]
    ]
    monthly = con.execute("""
        SELECT substr(ERDAT, 1, 4) || '-' || substr(ERDAT, 5, 2) AS m, COUNT(*) FROM VBAK
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    assert monthly == [(r["month"], r["orders"]) for r in kpis["monthly_order_counts"]]


def test_top_open_customers_need_the_leading_zero_normalization(env: tuple[Any, Path]) -> None:
    con, gold = env
    rows = con.execute("""
        SELECT c.KUNNR, SUM(b.DMBTR) AS total FROM BSID b
        JOIN KNA1 c ON lpad(b.KUNNR, 10, '0') = c.KUNNR
        GROUP BY 1 ORDER BY total DESC, c.KUNNR LIMIT 10
    """).fetchall()
    expected = [
        (r["customer_id"], Decimal(r["total"]))
        for r in load(gold, "kpis.json")["aging_top_customers"]
    ]
    assert rows == expected
    raw = con.execute("SELECT COUNT(*) FROM BSID b JOIN KNA1 c ON b.KUNNR = c.KUNNR").fetchone()
    assert raw == (0,)


def test_question_answers_match_sql(env: tuple[Any, Path]) -> None:
    con, gold = env
    orphan = con.execute(
        "SELECT COUNT(*) FROM VBAP p LEFT JOIN MARA m ON p.MATNR = m.MATNR WHERE m.MATNR IS NULL"
    ).fetchone()
    assert [list(orphan)] == question(gold, "orphan_items")["rows"]
    no_open = con.execute("""
        SELECT COUNT(*) FROM KNA1 c
        WHERE NOT EXISTS (SELECT 1 FROM BSID b WHERE lpad(b.KUNNR, 10, '0') = c.KUNNR)
    """).fetchone()
    assert [list(no_open)] == question(gold, "customers_without_open_items")["rows"]
    top_overdue = con.execute(f"""
        SELECT c.KUNNR, SUM(b.DMBTR) AS v FROM BSID b
        JOIN KNA1 c ON lpad(b.KUNNR, 10, '0') = c.KUNNR
        WHERE {OVERDUE_DAYS} > 0 GROUP BY 1 ORDER BY v DESC, c.KUNNR LIMIT 5
    """).fetchall()
    gold_rows = question(gold, "top_overdue_customers")["rows"]
    assert [[cid, float(v)] for cid, v in top_overdue] == gold_rows


def test_true_joins_hold_and_fan_out_trap_is_real(env: tuple[Any, Path]) -> None:
    con, gold = env
    edges = {(e["from"], e["to"]): e for e in load(gold, "joins.json")["edges"]}
    unmatched = con.execute("""
        SELECT COUNT(*) FROM BSID b WHERE b.KUNNR IS NOT NULL
        AND lpad(b.KUNNR, 10, '0') NOT IN (SELECT KUNNR FROM KNA1)
    """).fetchone()
    assert unmatched == (edges[("BSID.KUNNR", "KNA1.KUNNR")]["orphan_rows"],)
    fan_out = (
        con.execute("""
        SELECT COUNT(*) FROM VBAP p JOIN MAKT t ON p.MATNR = t.MATNR
    """).fetchone()[0]
        / con.execute("SELECT COUNT(*) FROM VBAP p JOIN MARA m ON p.MATNR = m.MATNR").fetchone()[0]
    )
    assert fan_out == 2.0
