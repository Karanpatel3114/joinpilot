import pyarrow as pa
import pytest

from joinpilot.synth.naming import SAP_COLUMNS, SAP_TABLES, qualified, rename


def test_every_table_has_a_sap_name_and_unique_sap_columns() -> None:
    assert set(SAP_TABLES) == set(SAP_COLUMNS)
    for columns in SAP_COLUMNS.values():
        assert len(set(columns.values())) == len(columns)
        assert all(name.isupper() for name in columns.values())


def test_sap_mode_renames_table_and_columns() -> None:
    data = pa.table({"customer_id": ["0000100001"], "customer_name": ["Oakridge Supply LLC"]})
    name, renamed = rename("customers", data, "sap")
    assert name == "KNA1"
    assert renamed.column_names == ["KUNNR", "NAME1"]
    assert renamed.column("KUNNR").to_pylist() == ["0000100001"]


def test_friendly_mode_keeps_canonical_names() -> None:
    data = pa.table({"order_id": ["0005000000"]})
    name, renamed = rename("order_headers", data, "friendly")
    assert (name, renamed.column_names) == ("order_headers", ["order_id"])


@pytest.mark.parametrize(
    ("naming", "expected"),
    [("sap", "BSID.KUNNR"), ("friendly", "open_items.customer_id")],
)
def test_qualified_names_match_the_api_format(naming: str, expected: str) -> None:
    assert qualified("open_items", "customer_id", naming) == expected  # type: ignore[arg-type]


def test_unknown_column_raises_key_error() -> None:
    with pytest.raises(KeyError):
        rename("customers", pa.table({"not_a_column": [1]}), "sap")
