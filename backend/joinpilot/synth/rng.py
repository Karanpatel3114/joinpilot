"""Independent, reproducible random streams.

Each table or planted issue gets its own stream derived from the seed and a name,
so adding a new issue never shifts the random numbers another table sees.
"""

from __future__ import annotations

import zlib
from datetime import date, timedelta

import numpy as np


def stream(seed: int, name: str) -> np.random.Generator:
    """Return a generator that depends only on `seed` and the stream `name`."""
    return np.random.default_rng([seed, zlib.crc32(name.encode("utf-8"))])


def random_dates(rng: np.random.Generator, start: date, end: date, n: int) -> list[date]:
    """Draw `n` dates uniformly between `start` and `end`, both inclusive."""
    offsets = rng.integers(0, (end - start).days + 1, size=n)
    return [start + timedelta(days=int(offset)) for offset in offsets]


def zipf_weights(n: int, exponent: float = 1.1) -> np.ndarray:
    """Weights that make a few entities very popular, as in real sales data."""
    ranks = np.arange(1, n + 1, dtype=np.float64)
    weights = 1.0 / ranks**exponent
    return weights / weights.sum()
