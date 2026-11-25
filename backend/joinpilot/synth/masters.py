"""Customer and product master tables (canonical, readable column names).

Names come from small generic word lists, so no real company or product appears.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pyarrow as pa

from joinpilot.synth.rng import random_dates, stream

COUNTRIES: dict[str, tuple[float, list[str], list[str]]] = {
    # country: (share, cities, legal suffixes)
    "US": (0.50, ["Chicago", "Houston", "Denver", "Atlanta", "Seattle", "Boston"], ["Inc.", "LLC"]),
    "DE": (0.20, ["Berlin", "Hamburg", "Munich", "Cologne", "Leipzig"], ["GmbH", "AG"]),
    "GB": (0.10, ["London", "Manchester", "Leeds", "Bristol"], ["Ltd", "PLC"]),
    "FR": (0.10, ["Paris", "Lyon", "Lille", "Nantes"], ["SA", "SARL"]),
    "IN": (0.10, ["Mumbai", "Pune", "Chennai", "Bengaluru"], ["Pvt Ltd", "Ltd"]),
}
NAME_PREFIXES = [
    "Al", "Bel", "Cor", "Dal", "Ever", "Fair", "Gran", "Hal", "Iron", "Jun", "Kel", "Lum",
    "Mar", "Nor", "Oak", "Pin", "Quin", "Ros", "Sil", "Tor", "Ul", "Ver", "Wes", "Yar", "Zen",
]  # fmt: skip
NAME_CORES = [
    "brook", "crest", "dale", "field", "gate", "haven", "ridge", "stone", "wood", "view",
    "point", "mont", "ford", "wick", "ton",
]  # fmt: skip
NAME_REGIONS = [
    "", "North ", "South ", "East ", "West ", "Global ", "United ", "Pacific ", "Central ",
    "Atlantic ", "Alpine ",
]  # fmt: skip
NAME_INDUSTRIES = [
    "Industrial", "Supply", "Trading", "Logistics", "Components", "Systems", "Engineering",
    "Manufacturing", "Distribution", "Technologies",
]  # fmt: skip
ACCOUNT_GROUPS = ["0001", "0002", "0003"]

# product group code: (English noun, German noun)
PRODUCT_GROUPS: dict[str, tuple[str, str]] = {
    "ELEC": ("Controller", "Steuerung"),
    "TOOL": ("Drill", "Bohrer"),
    "PUMP": ("Pump", "Pumpe"),
    "VALV": ("Valve", "Ventil"),
    "SENS": ("Sensor", "Sensor"),
    "CABL": ("Cable", "Kabel"),
    "MOTR": ("Motor", "Motor"),
    "BEAR": ("Bearing", "Lager"),
    "FILT": ("Filter", "Filter"),
    "SAFE": ("Safety Glove", "Schutzhandschuh"),
}
ADJECTIVES = [
    ("Compact", "Kompakt"), ("Heavy-duty", "Schwerlast"), ("Precision", "Präzisions"),
    ("Industrial", "Industrie"), ("Smart", "Smart"), ("Modular", "Modular"),
    ("Portable", "Tragbar"), ("High-flow", "Hochleistungs"),
]  # fmt: skip
PRODUCT_TYPES = (["FERT", "HAWA", "DIEN"], [0.55, 0.35, 0.10])
BASE_UNITS = ["EA", "KG", "M", "L", "BOX"]
LANGUAGES = ["E", "D"]


@dataclass(frozen=True)
class ProductMaster:
    """Products, their texts (one row per language) and list prices in cents."""

    products: pa.Table
    texts: pa.Table
    list_price_cents: np.ndarray


def zero_padded_ids(rng: np.random.Generator, n: int, low: int, high: int, width: int) -> list[str]:
    """Return `n` distinct, sorted numbers in [low, high) as zero-padded strings."""
    numbers = np.sort(rng.choice(np.arange(low, high), size=n, replace=False))
    return [str(int(x)).zfill(width) for x in numbers]


def make_customers(seed: int, n: int) -> pa.Table:
    """Generate the customer master with unique names and 10-character ids."""
    rng = stream(seed, "customers")
    countries = list(COUNTRIES)
    shares = np.array([COUNTRIES[c][0] for c in countries])
    country_idx = rng.choice(len(countries), size=n, p=shares / shares.sum())
    name_space = len(NAME_PREFIXES) * len(NAME_CORES) * len(NAME_REGIONS) * len(NAME_INDUSTRIES)
    name_codes = rng.choice(name_space, size=n, replace=False)
    names: list[str] = []
    cities: list[str] = []
    for code, ci in zip(name_codes, country_idx, strict=True):
        code = int(code)
        code, industry = divmod(code, len(NAME_INDUSTRIES))
        code, region = divmod(code, len(NAME_REGIONS))
        prefix, core = divmod(code, len(NAME_CORES))
        _, city_list, suffixes = COUNTRIES[countries[ci]]
        suffix = suffixes[int(rng.integers(len(suffixes)))]
        names.append(
            f"{NAME_REGIONS[region]}{NAME_PREFIXES[prefix]}{NAME_CORES[core]} "
            f"{NAME_INDUSTRIES[industry]} {suffix}"
        )
        cities.append(city_list[int(rng.integers(len(city_list)))])
    return pa.table(
        {
            "customer_id": zero_padded_ids(rng, n, 100_000, 1_000_000, 10),
            "customer_name": names,
            "country_code": [countries[i] for i in country_idx],
            "city": cities,
            "account_group": [ACCOUNT_GROUPS[i] for i in rng.integers(3, size=n)],
            "created_on": pa.array(
                random_dates(rng, date(2015, 1, 1), date(2024, 12, 31), n), pa.date32()
            ),
        }
    )


def make_products(seed: int, n: int) -> ProductMaster:
    """Generate the product master, two text rows per product and list prices."""
    rng = stream(seed, "products")
    groups = list(PRODUCT_GROUPS)
    group_idx = rng.integers(len(groups), size=n)
    adjective_idx = rng.integers(len(ADJECTIVES), size=n)
    model_numbers = rng.integers(100, 1000, size=n)
    ids = zero_padded_ids(rng, n, 10_000_000, 100_000_000, 18)
    products = pa.table(
        {
            "product_id": ids,
            "product_type": list(rng.choice(PRODUCT_TYPES[0], size=n, p=PRODUCT_TYPES[1])),
            "product_group": [groups[i] for i in group_idx],
            "base_unit": [BASE_UNITS[i] for i in rng.integers(len(BASE_UNITS), size=n)],
            "created_on": pa.array(
                random_dates(rng, date(2012, 1, 1), date(2024, 12, 31), n), pa.date32()
            ),
        }
    )
    text_ids: list[str] = []
    text_langs: list[str] = []
    descriptions: list[str] = []
    for i, product_id in enumerate(ids):
        group = groups[group_idx[i]]
        model = f"{group[:2]}-{int(model_numbers[i])}"
        for lang_pos, lang in enumerate(LANGUAGES):
            adjective = ADJECTIVES[adjective_idx[i]][lang_pos]
            noun = PRODUCT_GROUPS[group][lang_pos]
            text_ids.append(product_id)
            text_langs.append(lang)
            descriptions.append(f"{adjective} {noun} {model}")
    texts = pa.table({"product_id": text_ids, "language": text_langs, "description": descriptions})
    prices = np.round(rng.lognormal(mean=np.log(8_000), sigma=0.9, size=n)).astype(np.int64)
    return ProductMaster(products, texts, np.maximum(prices, 100))
