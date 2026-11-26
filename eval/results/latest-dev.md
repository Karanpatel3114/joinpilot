# Evaluation: dev split

- Date: 2026-11-26T02:26:18+00:00
- Commit: `fb92e1f`
- Datasets: `erp_s1_sap`, `erp_s2_sap`, `erp_s3_sap`, `erp_s1_friendly`
- Settings: recorded in metrics.json

## Join discovery

| System | Precision | Recall | F1 | Undirected F1 | Normalization recall | Fan-out recall | Fan-out precision | Decoy rejection |
|---|---|---|---|---|---|---|---|---|
| name_only | 0.370 | 1.000 | 0.540 | 0.690 | 0.000 | 0.000 | n/a | 0.800 |
| overlap_only | 0.274 | 0.850 | 0.415 | 0.515 | 1.000 | 0.000 | n/a | 0.600 |
| inclusion_dependency | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | n/a | 1.000 |
| joinpilot_deterministic | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

### Errors by system

- **name_only**: 34 false positives, 0 false negatives
  - erp_s1_sap: BSID.KUNNR -> VBAK.KUNNR
  - erp_s1_sap: BSID.BELNR -> VBAK.VBELN
  - erp_s1_sap: BSID.BELNR -> VBAP.VBELN
  - erp_s1_sap: BSID.WAERS -> VBAK.WAERK
  - erp_s1_sap: MARA.MATNR -> MAKT.MATNR
  - erp_s1_sap: VBAK.VBELN -> VBAP.VBELN
  - erp_s1_sap: VBAK.KUNNR -> BSID.KUNNR
  - erp_s1_sap: VBAK.WAERK -> BSID.WAERS
- **overlap_only**: 45 false positives, 3 false negatives
  - erp_s1_sap: BSID.BUKRS -> VBAK.VKORG
  - erp_s1_sap: BSID.BUZEI -> KNA1.KTOKD
  - erp_s1_sap: BSID.BUZEI -> VBAP.KWMENG
  - erp_s1_sap: BSID.BUZEI -> VBAP.POSNR
  - erp_s1_sap: BSID.WAERS -> VBAK.WAERK
  - erp_s1_sap: KNA1.KTOKD -> BSID.BUZEI
  - erp_s1_sap: KNA1.KTOKD -> VBAP.KWMENG
  - erp_s1_sap: KNA1.KTOKD -> VBAP.POSNR
  - erp_s1_sap: VBAP.MATNR -> MARA.MATNR
  - erp_s2_sap: VBAP.MATNR -> MARA.MATNR
  - erp_s1_friendly: order_items.product_id -> products.product_id
- **inclusion_dependency**: 0 false positives, 0 false negatives
- **joinpilot_deterministic**: 0 false positives, 0 false negatives

## Views and SIT checks (deterministic agent, no model)

| Reviewer | Views valid | Checks passed (first try) | Checks passed (final) | Avg repair attempts | Views repaired |
|---|---|---|---|---|---|
| approve_all | 1.000 | 1.000 | 1.000 | 0.0 | 0 |
| oracle | 1.000 | 1.000 | 1.000 | 0.0 | 0 |

## KPI correctness (recommended joins approved)

- Values right: 416 of 416 (100.0%); counts exact, money within 0.01%

| Dataset | aging_buckets | revenue_2026_by_product_group | monthly_order_counts | top_customers_by_revenue | aging_top_customers |
|---|---|---|---|---|---|
| erp_s1_sap | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_s2_sap | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_s3_sap | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |
| erp_s1_friendly | 5/5 | 11/11 | 18/18 | 10/10 | 60/60 |

## SQL safety

- Attacks blocked: 100.0% of 63
- Harmless queries wrongly blocked: 0.0% of 11
