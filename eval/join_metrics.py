"""Join discovery metrics against gold.

The unit is a directed column pair (from, to), with the many side first. Every
gold edge stays in its denominator: a join a system missed counts against its
recall, its normalization recall and its fan-out recall. Composite gold edges
(two-column keys) count as gold edges that single-column systems miss.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from eval.gold import GoldJoins

COUNT_FIELDS = (
    "predicted",
    "gold",
    "true_positives",
    "undirected_predicted",
    "undirected_true_positives",
    "normalization_needed",
    "normalization_found",
    "wrong_normalizations",
    "fan_out_total",
    "fan_out_found",
    "fan_out_flags",
    "fan_out_correct_flags",
    "filters_total",
    "filters_correct",
    "decoys_total",
    "decoys_rejected",
)


@dataclass(frozen=True)
class PredictedEdge:
    """One join a system proposes."""

    from_: str
    to: str
    normalization: str = "none"
    fan_out: bool = False
    filter: tuple[str, str] | None = None


@dataclass
class JoinCounts:
    """Counts that add up across datasets (micro-averaging)."""

    predicted: int = 0
    gold: int = 0
    true_positives: int = 0
    undirected_predicted: int = 0
    undirected_true_positives: int = 0
    normalization_needed: int = 0
    normalization_found: int = 0
    wrong_normalizations: int = 0
    fan_out_total: int = 0
    fan_out_found: int = 0
    fan_out_flags: int = 0
    fan_out_correct_flags: int = 0
    filters_total: int = 0
    filters_correct: int = 0
    decoys_total: int = 0
    decoys_rejected: int = 0
    false_positives: list[str] = field(default_factory=list)
    false_negatives: list[str] = field(default_factory=list)

    def add(self, other: JoinCounts) -> None:
        """Add another dataset's counts to these."""
        for name in COUNT_FIELDS:
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.false_positives += other.false_positives
        self.false_negatives += other.false_negatives

    def metrics(self) -> dict[str, float | int | None]:
        """Rates with their denominators kept honest (None when a rate is undefined)."""

        def rate(found: int, total: int) -> float | None:
            return round(found / total, 4) if total else None

        def f1(tp: int, predicted: int, gold: int) -> float:
            p = tp / predicted if predicted else 0.0
            r = tp / gold if gold else 0.0
            return round(2 * p * r / (p + r), 4) if p + r else 0.0

        undirected_gold = self.gold
        return {
            "precision": rate(self.true_positives, self.predicted) or 0.0,
            "recall": rate(self.true_positives, self.gold) or 0.0,
            "f1": f1(self.true_positives, self.predicted, self.gold),
            "undirected_f1": f1(
                self.undirected_true_positives, self.undirected_predicted, undirected_gold
            ),
            "predicted": self.predicted,
            "gold": self.gold,
            "true_positives": self.true_positives,
            "normalization_recall": rate(self.normalization_found, self.normalization_needed),
            "wrong_normalizations": self.wrong_normalizations,
            "fan_out_recall": rate(self.fan_out_found, self.fan_out_total),
            "fan_out_precision": rate(self.fan_out_correct_flags, self.fan_out_flags),
            "filter_accuracy": rate(self.filters_correct, self.filters_total),
            "decoy_rejection": rate(self.decoys_rejected, self.decoys_total),
        }


def score_dataset(dataset_id: str, predicted: list[PredictedEdge], gold: GoldJoins) -> JoinCounts:
    """Compare one system's edges with the gold edges of one dataset."""
    gold_by_pair = {(e.from_, e.to): e for e in gold.edges}
    predicted_by_pair = {(e.from_, e.to): e for e in predicted}
    gold_undirected = {frozenset(pair) for pair in gold_by_pair}
    predicted_undirected = {frozenset(pair) for pair in predicted_by_pair}
    counts = JoinCounts(
        predicted=len(predicted_by_pair),
        gold=len(gold_by_pair) + len(gold.composite_edges),
        undirected_predicted=len(predicted_undirected),
        undirected_true_positives=len(predicted_undirected & gold_undirected),
    )
    for pair, edge in predicted_by_pair.items():
        truth = gold_by_pair.get(pair)
        if edge.fan_out:
            counts.fan_out_flags += 1
            counts.fan_out_correct_flags += int(truth is not None and truth.fan_out)
        if truth is None:
            counts.false_positives.append(f"{dataset_id}: {pair[0]} -> {pair[1]}")
            continue
        counts.true_positives += 1
        counts.wrong_normalizations += int(edge.normalization != truth.normalization)
    for pair, truth in gold_by_pair.items():
        found = predicted_by_pair.get(pair)
        if found is None:
            counts.false_negatives.append(f"{dataset_id}: {pair[0]} -> {pair[1]}")
        if truth.normalization != "none":
            counts.normalization_needed += 1
            counts.normalization_found += int(
                found is not None and found.normalization == truth.normalization
            )
        if truth.fan_out:
            counts.fan_out_total += 1
            counts.fan_out_found += int(found is not None and found.fan_out)
        if truth.filter is not None:
            counts.filters_total += 1
            expected = (truth.filter.column, truth.filter.value)
            counts.filters_correct += int(found is not None and found.filter == expected)
    for composite in gold.composite_edges:
        source, target = composite.label
        counts.false_negatives.append(f"{dataset_id}: {source} -> {target} (composite)")
    for decoy in gold.decoys:
        counts.decoys_total += 1
        hit = (decoy.a, decoy.b) in predicted_by_pair or (decoy.b, decoy.a) in predicted_by_pair
        counts.decoys_rejected += int(not hit)
    return counts
