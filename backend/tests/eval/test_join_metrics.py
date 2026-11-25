from eval.gold import GoldDecoy, GoldEdge, GoldJoins
from eval.join_metrics import JoinCounts, PredictedEdge, score_dataset

GOLD = GoldJoins(
    dataset_id="d",
    edges=[
        GoldEdge(from_="A.k", to="B.k", normalization="none", fan_out=False),
        GoldEdge(from_="C.k", to="B.k", normalization="lpad_zeros:10", fan_out=False),
        GoldEdge(from_="T.k", to="B.k", normalization="none", fan_out=True),
    ],
    decoys=[GoldDecoy(a="A.cur", b="C.cur", reason="currency")],
)


def test_perfect_prediction_scores_one_everywhere() -> None:
    predicted = [
        PredictedEdge("A.k", "B.k"),
        PredictedEdge("C.k", "B.k", "lpad_zeros:10"),
        PredictedEdge("T.k", "B.k", fan_out=True),
    ]
    m = score_dataset("d", predicted, GOLD).metrics()
    assert (m["precision"], m["recall"], m["f1"]) == (1.0, 1.0, 1.0)
    assert (m["normalization_accuracy"], m["fan_out_recall"], m["decoy_rejection"]) == (
        1.0,
        1.0,
        1.0,
    )


def test_reversed_edges_and_decoys_count_as_false_positives() -> None:
    predicted = [
        PredictedEdge("B.k", "A.k"),
        PredictedEdge("C.cur", "A.cur"),
        PredictedEdge("C.k", "B.k"),
    ]
    counts = score_dataset("d", predicted, GOLD)
    m = counts.metrics()
    assert (m["precision"], m["recall"]) == (round(1 / 3, 4), round(1 / 3, 4))
    assert m["normalization_accuracy"] == 0.0
    assert m["fan_out_recall"] == 0.0
    assert m["decoy_rejection"] == 0.0
    assert counts.false_positives == ["d: B.k -> A.k", "d: C.cur -> A.cur"]
    assert len(counts.false_negatives) == 2


def test_counts_add_up_across_datasets_and_empty_predictions_are_zero() -> None:
    total = JoinCounts()
    total.add(score_dataset("d1", [PredictedEdge("A.k", "B.k")], GOLD))
    total.add(score_dataset("d2", [], GOLD))
    m = total.metrics()
    assert (m["predicted"], m["gold"], m["true_positives"]) == (1, 6, 1)
    assert m["precision"] == 1.0
    assert score_dataset("d3", [], GOLD).metrics()["f1"] == 0.0


def test_dev_split_ids_and_test_split_includes_tpch() -> None:
    from eval.datasets import split_ids

    assert split_ids("dev") == ["erp_s1_sap", "erp_s2_sap", "erp_s3_sap", "erp_s1_friendly"]
    assert split_ids("test")[-1] == "tpch_sf0.1"
