"""Join discovery metrics against gold: precision, recall, F1 and issue detection.

The unit is a directed column pair (from, to), with the many side first.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from eval.gold import GoldJoins


@dataclass(frozen=True)
class PredictedEdge:
    """One join a system proposes."""

    from_: str
    to: str
    normalization: str = "none"
    fan_out: bool = False


COUNT_FIELDS = (
    "predicted",
    "gold",
    "true_positives",
    "normalization_correct",
    "normalization_total",
    "fan_out_found",
    "fan_out_total",
    "decoys_rejected",
    "decoys_total",
)


@dataclass
class JoinCounts:
    """Counts that add up across datasets (micro-averaging)."""

    predicted: int = 0
    gold: int = 0
    true_positives: int = 0
    normalization_correct: int = 0
    normalization_total: int = 0
    fan_out_found: int = 0
    fan_out_total: int = 0
    decoys_rejected: int = 0
    decoys_total: int = 0
    false_positives: list[str] = field(default_factory=list)
    false_negatives: list[str] = field(default_factory=list)

    def add(self, other: JoinCounts) -> None:
        """Add another dataset's counts to these."""
        for name in COUNT_FIELDS:
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.false_positives += other.false_positives
        self.false_negatives += other.false_negatives

    def metrics(self) -> dict[str, float | int | None]:
        """Precision, recall, F1 and issue-detection rates (None when undefined)."""
        p = self.true_positives / self.predicted if self.predicted else 0.0
        r = self.true_positives / self.gold if self.gold else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0

        def rate(found: int, total: int) -> float | None:
            return round(found / total, 4) if total else None

        return {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "predicted": self.predicted,
            "gold": self.gold,
            "true_positives": self.true_positives,
            "normalization_accuracy": rate(self.normalization_correct, self.normalization_total),
            "fan_out_recall": rate(self.fan_out_found, self.fan_out_total),
            "decoy_rejection": rate(self.decoys_rejected, self.decoys_total),
        }


def score_dataset(dataset_id: str, predicted: list[PredictedEdge], gold: GoldJoins) -> JoinCounts:
    """Compare one system's edges with the gold edges of one dataset."""
    gold_by_pair = {(e.from_, e.to): e for e in gold.edges}
    predicted_by_pair = {(e.from_, e.to): e for e in predicted}
    counts = JoinCounts(predicted=len(predicted_by_pair), gold=len(gold_by_pair))
    for pair, edge in predicted_by_pair.items():
        truth = gold_by_pair.get(pair)
        if truth is None:
            counts.false_positives.append(f"{dataset_id}: {pair[0]} -> {pair[1]}")
            continue
        counts.true_positives += 1
        counts.normalization_total += 1
        counts.normalization_correct += int(edge.normalization == truth.normalization)
    for pair, truth in gold_by_pair.items():
        found = predicted_by_pair.get(pair)
        if found is None:
            counts.false_negatives.append(f"{dataset_id}: {pair[0]} -> {pair[1]}")
        if truth.fan_out:
            counts.fan_out_total += 1
            counts.fan_out_found += int(found is not None and found.fan_out)
    for decoy in gold.decoys:
        counts.decoys_total += 1
        hit = (decoy.a, decoy.b) in predicted_by_pair or (decoy.b, decoy.a) in predicted_by_pair
        counts.decoys_rejected += int(not hit)
    return counts
