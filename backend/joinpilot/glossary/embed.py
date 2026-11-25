"""Local text embeddings: hashed word and character-trigram features (no API, no quota).

Lexical rather than semantic, but deterministic, free and good at matching business
words to column descriptions ("customer" finds "customer number"). The vector size
is fixed by the database column.
"""

from __future__ import annotations

import hashlib
import math
import re

DIMENSIONS = 256
WORD_WEIGHT = 1.0
TRIGRAM_WEIGHT = 0.5
CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def tokens(text: str) -> list[tuple[str, float]]:
    """Words (split on separators and camelCase) and their character trigrams, with weights."""
    words = [w for w in re.split(r"[^a-z0-9]+", CAMEL.sub(" ", text).lower()) if w]
    features = [(f"w:{w}", WORD_WEIGHT) for w in words]
    for word in words:
        padded = f"^{word}$"
        features += [(f"t:{padded[i : i + 3]}", TRIGRAM_WEIGHT) for i in range(len(padded) - 2)]
    return features


def embed(text: str) -> list[float]:
    """A unit-length vector for `text`; the same text always gives the same vector."""
    vector = [0.0] * DIMENSIONS
    for feature, weight in tokens(text):
        digest = int.from_bytes(hashlib.blake2b(feature.encode(), digest_size=8).digest(), "big")
        sign = 1.0 if digest >> 63 else -1.0
        vector[digest % DIMENSIONS] += sign * weight
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / norm, 6) for v in vector]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two unit vectors."""
    return sum(x * y for x, y in zip(a, b, strict=True))
