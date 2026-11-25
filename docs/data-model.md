# Synthetic ERP dataset

A seeded, deterministic generator in `backend/joinpilot/synth/` produces ERP-style tables with known ground truth. The SAP-style names are a public, generic naming style used for realism. Nothing here comes from any real company, client or project.

## Tables

Each table has two naming modes: `sap` (cryptic, harder) and `friendly` (readable).

| Table (sap / friendly) | Columns (sap / friendly) | Notes |
|---|---|---|
| KNA1 / customers | KUNNR / customer_id (10-character, zero-padded), NAME1 / customer_name, LAND1 / country_code, ORT01 / city, KTOKD / account_group, ERDAT / created_on | Customer master |
| MARA / products | MATNR / product_id (18-character, zero-padded), MTART / product_type, MATKL / product_group, MEINS / base_unit, ERSDA / created_on | Product master |
| MAKT / product_texts | MATNR / product_id, SPRAS / language, MAKTX / description | 2 languages per product, which creates a fan-out trap |
| VBAK / order_headers | VBELN / order_id (10-character), ERDAT / order_date (text `YYYYMMDD`), KUNNR / customer_id, VKORG / sales_org, WAERK / currency, NETWR / net_value | Sales order headers |
| VBAP / order_items | VBELN / order_id, POSNR / item_no (integer 1–5), MATNR / product_id, KWMENG / quantity, NETWR / net_value | Sales order items |
| BSID / open_items | BUKRS / company_code, KUNNR / customer_id (stored without leading zeros), GJAHR / fiscal_year, BELNR / document_no, BUZEI / line_no (integer 1–3), BLDAT / document_date, ZFBDT / baseline_date, ZBD1T / payment_days, DMBTR / amount, WAERS / currency | Customer open items (receivables) |

## True joins (written to gold)

| From | To | Cardinality | Normalization | Note |
|---|---|---|---|---|
| VBAK.KUNNR | KNA1.KUNNR | N:1 | none | |
| VBAP.VBELN | VBAK.VBELN | N:1 | none | |
| VBAP.MATNR | MARA.MATNR | N:1 | none | About 1% orphans |
| MAKT.MATNR | MARA.MATNR | N:1 | none | Needs a language filter (`SPRAS = 'E'`) to avoid fan-out |
| BSID.KUNNR | KNA1.KUNNR | N:1 | left-pad with zeros to 10 characters | Planted mismatch |

**Decoys** that look like joins but aren't: VBAK.NETWR with VBAP.NETWR (same name, different meaning; single-item orders share values), ERDAT in different tables and KNA1.ERDAT with MARA.ERSDA (dates), POSNR with BUZEI (small integers: every BUZEI value appears in POSNR), WAERK with WAERS (currency codes). Good evaluation rewards rejecting these.

**Types.** Ids are zero-padded strings (KUNNR 10 characters, MATNR 18, VBELN 10, BELNR 10). Money columns are exact `DECIMAL(15,2)`, generated as integer cents. Dates are `DATE`, except VBAK.ERDAT, which is `YYYYMMDD` text. Amounts are treated as already converted to the reporting currency; the currency columns are the document currency.

## Planted data-quality issues

The rates live in config (`SynthSettings.issues` in `backend/joinpilot/config.py`, overridable with `SYNTH__ISSUES__<NAME>`), not in code. The generator records exactly what it planted, and the gold files carry the counts.

| Issue | Default rate | Where | Config key |
|---|---|---|---|
| Leading-zero key mismatch | 100% of rows | BSID.KUNNR | `stripped_zeros_open_items` |
| Orphan keys | 1.0% / 0.5% | VBAP.MATNR / BSID.KUNNR | `orphan_order_items` / `orphan_open_items` |
| Near-duplicate customers | 0.5% | KNA1 (same name, country and city, different KUNNR) | `duplicate_customers` |
| Null keys | 0.3% | BSID.KUNNR | `null_key_open_items` |
| Dates stored as text | 100% | VBAK.ERDAT | structural |
| Fan-out trap | 2 rows per product (E and D) | MAKT | structural |
| Mixed currencies | about 10% EUR, the rest USD | VBAK.WAERK, BSID.WAERS | `eur_share` |

Orphan keys look like real keys (same width and number range) but are missing from the master. Popular customers and products follow a Zipf-like skew, so top-N KPIs are meaningful.

## Sizes

| Size | Customers | Products | Orders | Items (about) | Open items |
|---|---|---|---|---|---|
| S | 1,000 | 2,000 | 10,000 | 30,000 | 8,000 |
| M | 10,000 | 20,000 | 100,000 | 300,000 | 80,000 |
| L | 50,000 | 50,000 | 500,000 | 1,500,000 | 400,000 |

## Gold files (`data/gold/<dataset_id>/`)

- `manifest.json`: provenance. The data fingerprint, generator version and generator settings this gold was computed from. Evaluation regenerates the data and refuses to score it if the fingerprint differs.
- `joins.json`: the true join edges (with cardinality, normalization, the MAKT language filter `SPRAS = 'E'`, and orphan and null row counts), the decoys, and the planted duplicate-customer pairs.
- `kpis.json`: true values as of the reference date 2026-06-30:
  - open receivables by aging bucket, overall and for the top 10 customers by open amount. Days overdue = reference date − (baseline date + payment days). Buckets: `not_due` (≤ 0, due today or later), `1-30`, `31-60`, `61-90`, `90+`. The overall buckets include orphan and null-key items; the per-customer view uses the normalized join to KNA1.
  - 2026 revenue by product group: item net value for orders dated in 2026, with a left join to MARA, so orphan items form a `null` group
  - monthly order counts
  - top 10 customers by revenue (header net value, all orders; ties broken by customer id)
- `qa.jsonl`: 40 question and answer pairs from 25 templates. Each line has `id`, `template`, `question` (business words, never table names), `columns`, `rows`, `ordered` and `tags` (for example `normalization`, `orphans`, `null_keys`, `duplicates`). Money answers are exact two-decimal strings, as in kpis.json.

Gold is computed in plain Python from the generated rows. `backend/tests/synth/test_gold_consistency.py` recomputes the KPIs and 16 of the 25 templates with DuckDB SQL over the written Parquet files, and the two must match exactly. Split gold is always written with the default generator settings, and a test pins the fingerprint of `erp_s1_sap` so a library or platform change cannot silently invalidate the gold.

## Splits

- **Dev:** seeds 1–3, size S, `sap` naming, plus seed 1 in `friendly` naming.
- **Test:** seeds 101–103, sizes S and M, both naming modes, plus TPC-H at scale factor 0.1.

## Commands

```bash
# one dataset (Parquet + manifest.json), optionally with gold
uv run python -m joinpilot.synth.generate --seed 1 --size S --naming sap --out data/generated/erp_s1_sap
# gold for every dev and test dataset (committed under data/gold/)
uv run python -m joinpilot.synth.splits --gold data/gold
# TPC-H tables and gold
uv run python -m joinpilot.synth.tpch --sf 0.1 --out data/generated/tpch_sf0.1 --gold data/gold
```

Dataset ids are `erp_<size><seed>_<naming>`, for example `erp_s1_sap` or `erp_m101_friendly`. The manifest records the seed, size, naming, row counts, generator version and a SHA-256 fingerprint of every table's content.

## TPC-H

Generated locally with DuckDB's tpch extension (dbgen; the extension is downloaded once from DuckDB's repository). Its gold join graph is the standard TPC-H foreign-key graph: 9 single-column edges plus the composite lineitem (l_partkey, l_suppkey) → partsupp key, recorded separately. Numbers measured on it are not official, audited TPC-H results.

## Licenses

- The synthetic ERP data is produced by this repository's generator (MIT). No real company, client or employer data is used.
- TPC-H data is generated locally and is not redistributed in this repository. TPC-H is a trademark of the Transaction Processing Performance Council; see `data/benchmarks/README.md`.
