# Evaluation: dev split

- Date: 2026-11-27T06:29:35+00:00
- Commit: `7c4b16b`
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

## Question answering (execution accuracy, recommended joins approved)

Rows must equal gold's; answer columns are matched to gold columns by value, and extra columns are allowed.

- Right: 120 of 160 (75.0%); blocked: {'LLM_UNAVAILABLE': 10, 'QUERY_FAILED': 2}; average attempts: 1.02
- By tag: duplicates 93.8%, none 79.2%, normalization 40.0%, null_keys 75.0%, orphans 70.8%
  - wrong in erp_s1_sap: q004 How many products belong to product group BEAR?
  - wrong in erp_s1_sap: q005 How many products belong to product group CABL?
  - wrong in erp_s1_sap: q006 How many sales orders were created in February 2025?
  - wrong in erp_s1_sap: q009 What is the total net value of all sales orders created in 2025?
  - wrong in erp_s1_sap: q014 What is the total open receivables amount for customer 0000150179?
  - wrong in erp_s1_sap: q015 What is the total open receivables amount for customer 0000192391?
  - wrong in erp_s1_sap: q016 What is the total open receivables amount for customer 0000925437?
  - wrong in erp_s1_sap: q017 How many sales order items reference a product that does not exist in the product master?
  - wrong in erp_s1_sap: q029 How many customers in the customer master have no open receivables?
  - wrong in erp_s1_sap: q034 List the product IDs and total item net value of the 3 products with the highest item net value in 2026, highest first.
  - wrong in erp_s2_sap: q005 How many products belong to product group SAFE?
  - wrong in erp_s2_sap: q012 What is the total open receivables amount more than 90 days overdue as of June 30, 2026 (the due date is the baseline date plus the payment days)?
  - wrong in erp_s2_sap: q019 What was the total item net value in 2026 for products in product group TOOL?
  - wrong in erp_s2_sap: q022 How many sales orders did South Ashford Industrial LLC place in 2026?
  - wrong in erp_s2_sap: q029 How many customers in the customer master have no open receivables?
  - wrong in erp_s2_sap: q036 How many open receivable line items are not yet due as of June 30, 2026 (the due date is the baseline date plus the payment days)?
  - wrong in erp_s3_sap: q004 How many products belong to product group FILT?
  - wrong in erp_s3_sap: q005 How many products belong to product group VALV?
  - wrong in erp_s3_sap: q010 What is the total net value of all sales orders created in 2026?
  - wrong in erp_s3_sap: q012 What is the total open receivables amount more than 90 days overdue as of June 30, 2026 (the due date is the baseline date plus the payment days)?
  - wrong in erp_s3_sap: q014 What is the total open receivables amount for customer 0000107501?
  - wrong in erp_s3_sap: q015 What is the total open receivables amount for customer 0000466152?
  - wrong in erp_s3_sap: q016 What is the total open receivables amount for customer 0000842877?
  - wrong in erp_s3_sap: q022 How many sales orders did South Beldale Trading LLC place in 2026?
  - wrong in erp_s3_sap: q027 How many sales orders does each sales organization have?
  - wrong in erp_s3_sap: q029 How many customers in the customer master have no open receivables?
  - wrong in erp_s1_friendly: q003 How many customers are based in India?
  - wrong in erp_s1_friendly: q004 How many products belong to product group BEAR?
  - wrong in erp_s1_friendly: q005 How many products belong to product group CABL?
  - wrong in erp_s1_friendly: q006 How many sales orders were created in February 2025?
  - wrong in erp_s1_friendly: q009 What is the total net value of all sales orders created in 2025?
  - wrong in erp_s1_friendly: q010 What is the total net value of all sales orders created in 2026?
  - wrong in erp_s1_friendly: q015 What is the total open receivables amount for customer 0000192391?
  - wrong in erp_s1_friendly: q016 What is the total open receivables amount for customer 0000925437?
  - wrong in erp_s1_friendly: q029 How many customers in the customer master have no open receivables?
  - wrong in erp_s1_friendly: q030 What is the total ordered quantity of product 000000000042887125?

## SQL safety

- Attacks blocked: 100.0% of 71
- Harmless queries wrongly blocked: 0.0% of 11
