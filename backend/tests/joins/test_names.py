import pytest

from joinpilot.joins.names import name_similarity, stem, table_prefix


def test_tpch_style_prefixes_are_detected_and_stripped() -> None:
    assert table_prefix(["o_orderkey", "o_custkey", "o_totalprice"]) == "o_"
    assert stem("o_custkey", "o_") == "custkey"


def test_tables_without_a_shared_prefix_keep_full_names() -> None:
    assert table_prefix(["customer_id", "customer_name", "country_code", "city"]) == ""
    assert table_prefix(["KUNNR", "NAME1"]) == ""
    assert stem("Customer_ID", "") == "customerid"


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [("custkey", "custkey", 1.0), ("", "custkey", 0.0), ("waerk", "waers", 0.4)],
)
def test_equal_stems_score_one_and_fuzzy_matches_score_at_most_half(
    a: str, b: str, expected: float
) -> None:
    assert name_similarity(a, b) == expected
    assert name_similarity("linenumber", "nationkey") <= 0.5
