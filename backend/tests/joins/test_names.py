import pytest

from joinpilot.joins.names import name_similarity, singular, stem, table_prefix


def test_tpch_style_prefixes_are_detected_and_stripped() -> None:
    assert table_prefix(["o_orderkey", "o_custkey", "o_totalprice"], 0.8, 4) == "o_"
    assert stem("o_custkey", "o_") == "custkey"


def test_tables_without_a_shared_prefix_keep_full_names() -> None:
    assert table_prefix(["customer_id", "customer_name", "country_code", "city"], 0.8, 4) == ""
    assert table_prefix(["KUNNR", "NAME1"], 0.8, 4) == ""
    assert stem("Customer_ID", "") == "customerid"


@pytest.mark.parametrize(
    ("table", "expected"),
    [("customers", "customer"), ("categories", "category"), ("addresses", "address"),
     ("KNA1", "kna1"), ("class", "class")],
)  # fmt: skip
def test_singular_table_names(table: str, expected: str) -> None:
    assert singular(table) == expected


def test_generic_key_names_are_qualified_with_their_table() -> None:
    assert stem("id", "", "customers") == "customerid"
    assert stem("customer_id", "", "orders") == "customerid"
    assert stem("name", "", "customers") == "name"


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [("custkey", "custkey", 1.0), ("", "custkey", 0.0), ("waerk", "waers", 0.4)],
)
def test_equal_stems_score_one_and_fuzzy_matches_are_capped(
    a: str, b: str, expected: float
) -> None:
    assert name_similarity(a, b, fuzzy_weight=0.5) == expected
    assert name_similarity("linenumber", "nationkey", fuzzy_weight=0.5) <= 0.5
