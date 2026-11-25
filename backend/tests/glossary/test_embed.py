import math

from joinpilot.glossary.embed import DIMENSIONS, cosine, embed, tokens


def test_embeddings_are_deterministic_unit_vectors() -> None:
    vector = embed("customer number of customer master")
    assert vector == embed("customer number of customer master")
    assert len(vector) == DIMENSIONS
    assert math.isclose(sum(v * v for v in vector), 1.0, abs_tol=1e-4)


def test_related_texts_are_closer_than_unrelated_ones() -> None:
    query = embed("customer name")
    assert cosine(query, embed("name of customer master")) > cosine(query, embed("fiscal year"))


def test_tokens_split_camel_case_and_separators() -> None:
    words = {t for t, _ in tokens("ProductGroup_code") if t.startswith("w:")}
    assert words == {"w:product", "w:group", "w:code"}
