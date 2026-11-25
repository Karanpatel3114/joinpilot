"""Plain-English meanings of common SAP-style table and field names.

These are public, generic naming conventions (the same ones the synthetic data
uses for realism), not any company's data. Unknown names simply get no hint.
"""

from __future__ import annotations

TABLE_HINTS = {
    "KNA1": "customer master",
    "MARA": "material product master",
    "MAKT": "material product descriptions texts",
    "VBAK": "sales order header",
    "VBAP": "sales order item line",
    "BSID": "customer open items accounts receivable",
}

FIELD_HINTS = {
    "KUNNR": "customer number",
    "NAME1": "name",
    "LAND1": "country",
    "ORT01": "city",
    "KTOKD": "customer account group",
    "ERDAT": "created on date",
    "ERSDA": "created on date",
    "MATNR": "material product number",
    "MTART": "material product type",
    "MATKL": "material product group",
    "MEINS": "base unit of measure",
    "SPRAS": "language",
    "MAKTX": "material product description",
    "VBELN": "sales order document number",
    "VKORG": "sales organization",
    "WAERK": "document currency",
    "NETWR": "net value amount",
    "POSNR": "item number",
    "KWMENG": "order quantity",
    "BUKRS": "company code",
    "GJAHR": "fiscal year",
    "BELNR": "accounting document number",
    "BUZEI": "line item number",
    "BLDAT": "document date",
    "ZFBDT": "baseline date for the due date",
    "ZBD1T": "payment terms days",
    "DMBTR": "amount in local currency",
    "WAERS": "currency",
}
