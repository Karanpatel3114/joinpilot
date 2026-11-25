# Evaluation: dev split

- Date: 2026-11-25T22:35:55+00:00
- Commit: `85cc117`
- Datasets: `erp_s1_sap`, `erp_s2_sap`, `erp_s3_sap`, `erp_s1_friendly`

## Join discovery

| System | Precision | Recall | F1 | Normalization acc. | Fan-out recall | Decoy rejection |
|---|---|---|---|---|---|---|
| name_only | 0.370 | 1.000 | 0.540 | 0.800 | 0.000 | 0.800 |
| overlap_only | 0.274 | 0.850 | 0.415 | 1.000 | 0.000 | 0.600 |
| joinpilot_deterministic | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

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
- **joinpilot_deterministic**: 0 false positives, 0 false negatives
