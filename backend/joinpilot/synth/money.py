"""Exact money columns. Amounts are generated as integer cents, never floats."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

import pyarrow as pa

MONEY = pa.decimal128(15, 2)


def money_array(cents: Iterable[int]) -> pa.Array[pa.Scalar[pa.Decimal128Type]]:
    """Convert integer cents to an exact DECIMAL(15, 2) column."""
    return pa.array([Decimal(int(c)).scaleb(-2) for c in cents], MONEY)
