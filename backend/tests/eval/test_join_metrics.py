from eval.gold import GoldCompositeEdge, GoldDecoy, GoldEdge, GoldFilter, GoldJoins
from eval.join_metrics import JoinCounts, PredictedEdge, score_dataset


def edge(a: str, b: str, norm: str = "none", fan_out: bool = False, **extra: object) -> GoldEdge:
    return GoldEdge(from_=a, to=b, cardinality="N:1", normalization=norm, fan_out=fan_out, **extra)  # type: ignore[arg-type]


GOLD = GoldJoins(
    dataset_id="d",
    edges=[
        edge("A.k", "B.k"),
        edge("C.k", "B.k", "lpad_zeros:10"),
        edge("T.k", "B.k", fan_out=True, filter=GoldFilter(column="T.lang", value="E")),
    ],
    decoys=[GoldDecoy(a="A.cur", b="C.cur", reason="currency")],
)


def test_perfect_prediction_scores_one_everywhere() -> None:
    predicted = [
        PredictedEdge("A.k", "B.k"),
        PredictedEdge("C.k", "B.k", "lpad_zeros:10"),
        PredictedEdge("T.k", "B.k", fan_out=True, filter=("T.lang", "E")),
    ]
    m = score_dataset("d", predicted, GOLD).metrics()
    assert (m["precision"], m["recall"], m["f1"], m["undirected_f1"]) == (1.0, 1.0, 1.0, 1.0)
    assert (m["normalization_recall"], m["fan_out_recall"], m["fan_out_precision"]) == (
        1.0,
        1.0,
        1.0,
    )
    assert (m["filter_accuracy"], m["decoy_rejection"], m["wrong_normalizations"]) == (1.0, 1.0, 0)


def test_missed_joins_stay_in_every_denominator() -> None:
    m = score_dataset("d", [PredictedEdge("A.k", "B.k")], GOLD).metrics()
    assert m["recall"] == round(1 / 3, 4)
    assert m["normalization_recall"] == 0.0
    assert m["fan_out_recall"] == 0.0
    assert m["filter_accuracy"] == 0.0
    assert m["fan_out_precision"] is None


def test_reversed_edges_count_as_errors_but_not_undirected() -> None:
    predicted = [
        PredictedEdge("B.k", "A.k"),
        PredictedEdge("C.cur", "A.cur"),
        PredictedEdge("C.k", "B.k"),
    ]
    counts = score_dataset("d", predicted, GOLD)
    m = counts.metrics()
    assert (m["precision"], m["recall"]) == (round(1 / 3, 4), round(1 / 3, 4))
    assert m["undirected_f1"] > m["f1"]
    assert m["wrong_normalizations"] == 1
    assert m["decoy_rejection"] == 0.0
    assert counts.false_positives == ["d: B.k -> A.k", "d: C.cur -> A.cur"]


def test_false_fan_out_flags_lower_fan_out_precision() -> None:
    predicted = [
        PredictedEdge("A.k", "B.k", fan_out=True),
        PredictedEdge("T.k", "B.k", fan_out=True),
    ]
    assert score_dataset("d", predicted, GOLD).metrics()["fan_out_precision"] == 0.5


def test_composite_gold_edges_count_as_misses_for_single_column_systems() -> None:
    gold = GOLD.model_copy(
        update={"composite_edges": [GoldCompositeEdge(from_=["L.p", "L.s"], to=["PS.p", "PS.s"])]}
    )
    counts = score_dataset("d", [PredictedEdge("A.k", "B.k")], gold)
    assert counts.metrics()["gold"] == 4
    assert "d: L.p+L.s -> PS.p+PS.s (composite)" in counts.false_negatives


def test_counts_add_up_across_datasets_and_empty_predictions_are_zero() -> None:
    total = JoinCounts()
    total.add(score_dataset("d1", [PredictedEdge("A.k", "B.k")], GOLD))
    total.add(score_dataset("d2", [], GOLD))
    m = total.metrics()
    assert (m["predicted"], m["gold"], m["true_positives"]) == (1, 6, 1)
    assert m["precision"] == 1.0
    assert score_dataset("d3", [], GOLD).metrics()["f1"] == 0.0
