"""Naming modes: readable `friendly` names or cryptic SAP-style `sap` names.

Generation always uses the friendly (canonical) names; this module renames the
output. SAP-style names are a public naming convention used only for realism.
"""

from __future__ import annotations

from typing import Literal

import pyarrow as pa

Naming = Literal["sap", "friendly"]
NAMING_MODES: tuple[Naming, ...] = ("sap", "friendly")

SAP_TABLES: dict[str, str] = {
    "customers": "KNA1",
    "products": "MARA",
    "product_texts": "MAKT",
    "order_headers": "VBAK",
    "order_items": "VBAP",
    "open_items": "BSID",
}

SAP_COLUMNS: dict[str, dict[str, str]] = {
    "customers": {
        "customer_id": "KUNNR",
        "customer_name": "NAME1",
        "country_code": "LAND1",
        "city": "ORT01",
        "account_group": "KTOKD",
        "created_on": "ERDAT",
    },
    "products": {
        "product_id": "MATNR",
        "product_type": "MTART",
        "product_group": "MATKL",
        "base_unit": "MEINS",
        "created_on": "ERSDA",
    },
    "product_texts": {"product_id": "MATNR", "language": "SPRAS", "description": "MAKTX"},
    "order_headers": {
        "order_id": "VBELN",
        "order_date": "ERDAT",
        "customer_id": "KUNNR",
        "sales_org": "VKORG",
        "currency": "WAERK",
        "net_value": "NETWR",
    },
    "order_items": {
        "order_id": "VBELN",
        "item_no": "POSNR",
        "product_id": "MATNR",
        "quantity": "KWMENG",
        "net_value": "NETWR",
    },
    "open_items": {
        "company_code": "BUKRS",
        "customer_id": "KUNNR",
        "fiscal_year": "GJAHR",
        "document_no": "BELNR",
        "line_no": "BUZEI",
        "document_date": "BLDAT",
        "baseline_date": "ZFBDT",
        "payment_days": "ZBD1T",
        "amount": "DMBTR",
        "currency": "WAERS",
    },
}


def table_name(table: str, naming: Naming) -> str:
    """Return the output name of a canonical table."""
    return SAP_TABLES[table] if naming == "sap" else table


def column_name(table: str, column: str, naming: Naming) -> str:
    """Return the output name of a canonical column."""
    return SAP_COLUMNS[table][column] if naming == "sap" else column


def qualified(table: str, column: str, naming: Naming) -> str:
    """Return `TABLE.COLUMN` in the chosen naming mode, as used in gold and the API."""
    return f"{table_name(table, naming)}.{column_name(table, column, naming)}"


def rename(table: str, data: pa.Table, naming: Naming) -> tuple[str, pa.Table]:
    """Rename a canonical table and its columns for the chosen naming mode."""
    columns = [column_name(table, c, naming) for c in data.column_names]
    return table_name(table, naming), data.rename_columns(columns)
