# Evaluation: test split

- Date: 2026-11-26T08:18:22+00:00
- Commit: `1a22e17`
- Datasets: `erp_s101_sap`, `erp_s101_friendly`, `erp_m101_sap`, `erp_m101_friendly`, `erp_s102_sap`, `erp_s102_friendly`, `erp_m102_sap`, `erp_m102_friendly`, `erp_s103_sap`, `erp_s103_friendly`, `erp_m103_sap`, `erp_m103_friendly`, `tpch_sf0.1`
- Settings: recorded in metrics.json

## Join discovery

| System | Precision | Recall | F1 | Undirected F1 | Normalization recall | Fan-out recall | Fan-out precision | Decoy rejection |
|---|---|---|---|---|---|---|---|---|
| name_only | 0.274 | 0.986 | 0.429 | 0.600 | 0.000 | 0.000 | n/a | 0.800 |
| overlap_only | 0.213 | 0.871 | 0.343 | 0.411 | 1.000 | 0.000 | n/a | 0.600 |
| inclusion_dependency | 0.775 | 0.986 | 0.868 | 0.868 | 1.000 | 0.000 | n/a | 1.000 |
| joinpilot_deterministic | 1.000 | 0.986 | 0.993 | 0.993 | 1.000 | 1.000 | 1.000 | 1.000 |

### Errors by system

- **name_only**: 183 false positives, 1 false negatives
  - erp_s101_sap: BSID.KUNNR -> VBAK.KUNNR
  - erp_s101_sap: BSID.BELNR -> VBAK.VBELN
  - erp_s101_sap: BSID.BELNR -> VBAP.VBELN
  - erp_s101_sap: BSID.WAERS -> VBAK.WAERK
  - erp_s101_sap: MARA.MATNR -> MAKT.MATNR
  - erp_s101_sap: VBAK.VBELN -> VBAP.VBELN
  - erp_s101_sap: VBAK.KUNNR -> BSID.KUNNR
  - erp_s101_sap: VBAK.WAERK -> BSID.WAERS
  - tpch_sf0.1: lineitem.l_partkey+lineitem.l_suppkey -> partsupp.ps_partkey+partsupp.ps_suppkey (composite)
- **overlap_only**: 225 false positives, 9 false negatives
  - erp_s101_sap: BSID.BUKRS -> VBAK.VKORG
  - erp_s101_sap: BSID.BUZEI -> KNA1.KTOKD
  - erp_s101_sap: BSID.BUZEI -> VBAP.KWMENG
  - erp_s101_sap: BSID.BUZEI -> VBAP.POSNR
  - erp_s101_sap: BSID.WAERS -> VBAK.WAERK
  - erp_s101_sap: KNA1.KTOKD -> BSID.BUZEI
  - erp_s101_sap: KNA1.KTOKD -> VBAP.KWMENG
  - erp_s101_sap: KNA1.KTOKD -> VBAP.POSNR
  - erp_m101_sap: VBAP.MATNR -> MARA.MATNR
  - erp_m101_friendly: order_items.product_id -> products.product_id
  - erp_m102_sap: VBAP.MATNR -> MARA.MATNR
  - erp_m102_friendly: order_items.product_id -> products.product_id
  - erp_s103_sap: VBAP.MATNR -> MARA.MATNR
  - erp_s103_friendly: order_items.product_id -> products.product_id
  - erp_m103_sap: VBAP.MATNR -> MARA.MATNR
  - erp_m103_friendly: order_items.product_id -> products.product_id
- **inclusion_dependency**: 20 false positives, 1 false negatives
  - tpch_sf0.1: customer.c_nationkey -> part.p_partkey
  - tpch_sf0.1: customer.c_nationkey -> supplier.s_suppkey
  - tpch_sf0.1: lineitem.l_linenumber -> customer.c_custkey
  - tpch_sf0.1: lineitem.l_linenumber -> nation.n_nationkey
  - tpch_sf0.1: lineitem.l_linenumber -> orders.o_orderkey
  - tpch_sf0.1: lineitem.l_linenumber -> part.p_partkey
  - tpch_sf0.1: lineitem.l_linenumber -> supplier.s_suppkey
  - tpch_sf0.1: lineitem.l_suppkey -> customer.c_custkey
  - tpch_sf0.1: lineitem.l_partkey+lineitem.l_suppkey -> partsupp.ps_partkey+partsupp.ps_suppkey (composite)
- **joinpilot_deterministic**: 0 false positives, 1 false negatives
  - tpch_sf0.1: lineitem.l_partkey+lineitem.l_suppkey -> partsupp.ps_partkey+partsupp.ps_suppkey (composite)

## Views and SIT checks (deterministic agent, no model)

| Reviewer | Views valid | Checks passed (first try) | Checks passed (final) | Avg repair attempts | Views repaired |
|---|---|---|---|---|---|
| approve_all | 1.000 | 1.000 | 1.000 | 0.0 | 0 |
| oracle | 1.000 | 1.000 | 1.000 | 0.0 | 0 |

## KPI correctness (recommended joins approved)

- Values right: 1248 of 1248 (100.0%); counts exact, money within 0.01%

| Dataset | aging_buckets | revenue_2026_by_product_group | monthly_order_counts | top_customers_by_revenue | aging_top_customers |
|---|---|---|---|---|---|
| erp_s101_sap | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_s101_friendly | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_m101_sap | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_m101_friendly | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_s102_sap | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_s102_friendly | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_m102_sap | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_m102_friendly | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_s103_sap | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_s103_friendly | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_m103_sap | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_m103_friendly | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |

## Question answering

- Skipped: not run; it needs --llm and a GEMINI_API_KEY

## SQL safety

- Attacks blocked: 100.0% of 71
- Harmless queries wrongly blocked: 0.0% of 11
