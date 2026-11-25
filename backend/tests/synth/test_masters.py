from datetime import date

import pyarrow as pa

from joinpilot.synth.masters import LANGUAGES, PRODUCT_GROUPS, make_customers, make_products


def test_customers_have_unique_zero_padded_ids_and_names() -> None:
    customers = make_customers(seed=1, n=500)
    ids = customers.column("customer_id").to_pylist()
    names = customers.column("customer_name").to_pylist()
    assert customers.num_rows == 500
    assert len(set(ids)) == 500
    assert all(len(i) == 10 and i.isdigit() and i.startswith("0000") for i in ids)
    assert len(set(names)) == 500
    assert ids == sorted(ids)


def test_customer_columns_have_expected_types_and_ranges() -> None:
    customers = make_customers(seed=2, n=200)
    assert customers.schema.field("created_on").type == pa.date32()
    created = customers.column("created_on").to_pylist()
    assert all(date(2015, 1, 1) <= d <= date(2024, 12, 31) for d in created)
    assert set(customers.column("country_code").to_pylist()) <= {"US", "DE", "GB", "FR", "IN"}


def test_products_have_18_character_ids_and_known_groups() -> None:
    master = make_products(seed=1, n=300)
    ids = master.products.column("product_id").to_pylist()
    assert len(set(ids)) == 300
    assert all(len(i) == 18 and i.isdigit() for i in ids)
    assert set(master.products.column("product_group").to_pylist()) <= set(PRODUCT_GROUPS)
    assert len(master.list_price_cents) == 300
    assert int(master.list_price_cents.min()) >= 100


def test_every_product_has_exactly_one_text_per_language() -> None:
    texts = make_products(seed=3, n=50).texts.to_pylist()
    assert len(texts) == 50 * len(LANGUAGES)
    assert len({(row["product_id"], row["language"]) for row in texts}) == len(texts)
    german = [row["description"] for row in texts if row["language"] == "D"]
    assert all(row["description"] for row in texts)
    assert any(word in d for d in german for word in ("Pumpe", "Ventil", "Kabel", "Lager", "ä"))


def test_same_seed_gives_same_masters_and_other_seed_differs() -> None:
    assert make_customers(7, 100).equals(make_customers(7, 100))
    assert make_products(7, 100).products.equals(make_products(7, 100).products)
    assert not make_customers(7, 100).equals(make_customers(8, 100))
