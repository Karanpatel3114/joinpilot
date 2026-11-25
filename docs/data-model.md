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
| VBAP / order_items | VBELN / order_id, POSNR / item_no (6-digit), MATNR / product_id, KWMENG / quantity, NETWR / net_value | Sales order items |
| BSID / open_items | BUKRS / company_code, KUNNR / customer_id (stored without leading zeros), GJAHR / fiscal_year, BELNR / document_no, BUZEI / line_no, BLDAT / document_date, ZFBDT / baseline_date, ZBD1T / payment_days, DMBTR / amount, WAERS / currency | Customer open items (receivables) |

## True joins (written to gold)

| From | To | Cardinality | Normalization | Note |
|---|---|---|---|---|
| VBAK.KUNNR | KNA1.KUNNR | N:1 | none | |
| VBAP.VBELN | VBAK.VBELN | N:1 | none | |
| VBAP.MATNR | MARA.MATNR | N:1 | none | About 1% orphans |
| MAKT.MATNR | MARA.MATNR | N:1 | none | Needs a language filter (`SPRAS = 'E'`) to avoid fan-out |
| BSID.KUNNR | KNA1.KUNNR | N:1 | left-pad with zeros to 10 characters | Planted mismatch |

**Decoys** that look like joins but aren't: VBAK.NETWR with VBAP.NETWR (same name, different meaning), ERDAT in different tables (dates), POSNR with BUZEI (small integers that overlap by chance), WAERK with WAERS (currency codes). Good evaluation rewards rejecting these.

## Planted data-quality issues

The rates live in config, not in code.

| Issue | Default rate | Where |
|---|---|---|
| Leading-zero key mismatch | 100% of rows | BSID.KUNNR |
| Orphan keys | 1.0% / 0.5% | VBAP.MATNR / BSID.KUNNR |
| Near-duplicate customers | 0.5% | KNA1 (same name, different KUNNR) |
| Null keys | 0.3% | BSID.KUNNR |
| Dates stored as text | 100% | VBAK.ERDAT |
| Fan-out trap | 2 rows per product | MAKT |
| Mixed currencies | about 10% EUR, the rest USD | VBAK.WAERK, BSID.WAERS |

## Sizes

| Size | Customers | Products | Orders | Items (about) | Open items |
|---|---|---|---|---|---|
| S | 1,000 | 2,000 | 10,000 | 30,000 | 8,000 |
| M | 10,000 | 20,000 | 100,000 | 300,000 | 80,000 |
| L | 50,000 | 50,000 | 500,000 | 1,500,000 | 400,000 |

## Gold files (`data/gold/<dataset_id>/`)

- `joins.json`: the true join edges (with cardinality, normalization and filters) and the list of decoys.
- `kpis.json`: true values as of the reference date 2026-06-30:
  - open receivables by aging bucket (not due, 0–30, 31–60, 61–90 and over 90 days overdue, with the due date being the baseline date plus payment days), overall and for the top 10 customers
  - 2026 revenue by product group
  - monthly order counts
  - top 10 customers by revenue
- `qa.jsonl`: about 40 question and answer pairs from templates, each with the true result set.

## Splits

- **Dev:** seeds 1–3, size S, `sap` naming, plus seed 1 in `friendly` naming.
- **Test:** seeds 101–103, sizes S and M, both naming modes, plus TPC-H at scale factor 0.1.

## TPC-H

Generated with DuckDB's tpch extension. Its gold join graph is the standard TPC-H foreign-key graph.
