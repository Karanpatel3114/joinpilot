from joinpilot.config import JoinSettings
from joinpilot.joins.models import JoinCandidate
from joinpilot.joins.scoring import cardinality, raw_score, score_candidates
from joinpilot.profiling.models import ProjectProfile

SAP_TRUTH = {
    ("VBAK.KUNNR", "KNA1.KUNNR"),
    ("VBAP.VBELN", "VBAK.VBELN"),
    ("VBAP.MATNR", "MARA.MATNR"),
    ("MAKT.MATNR", "MARA.MATNR"),
    ("BSID.KUNNR", "KNA1.KUNNR"),
}


def accepted(profile: ProjectProfile) -> dict[tuple[str, str], JoinCandidate]:
    return {(c.from_, c.to): c for c in score_candidates(profile, JoinSettings()) if c.accepted}


def test_sample_erp_joins_are_found_with_normalization_and_fan_out(
    sap_profile: ProjectProfile,
) -> None:
    found = accepted(sap_profile)
    assert set(found) == SAP_TRUTH
    assert found[("BSID.KUNNR", "KNA1.KUNNR")].normalization == "lpad_zeros:10"
    makt = found[("MAKT.MATNR", "MARA.MATNR")]
    assert makt.fan_out_risk and makt.filter is not None
    assert (makt.filter.column, makt.filter.value) == ("MAKT.SPRAS", "E")
    assert makt.rows_per_key == 2.0
    assert not found[("VBAP.VBELN", "VBAK.VBELN")].fan_out_risk


def test_friendly_names_give_the_same_graph(friendly_profile: ProjectProfile) -> None:
    assert ("open_items.customer_id", "customers.customer_id") in accepted(friendly_profile)
    assert len(accepted(friendly_profile)) == 5


def test_decoys_are_rejected_with_a_reason(sap_profile: ProjectProfile) -> None:
    ranked = {(c.from_, c.to): c for c in score_candidates(sap_profile, JoinSettings())}
    currency = ranked[("VBAK.WAERK", "BSID.WAERS")]
    assert not currency.accepted
    assert currency.cardinality == "N:M"
    assert "neither side is unique" in (currency.rejection_reason or "")
    reverse = ranked[("KNA1.KUNNR", "VBAK.KUNNR")]
    assert not reverse.accepted
    assert reverse.cardinality == "1:N"


def test_edge_ids_follow_the_ranking(sap_profile: ProjectProfile) -> None:
    ranked = score_candidates(sap_profile, JoinSettings())
    assert [c.edge_id for c in ranked] == [f"e{i}" for i in range(1, len(ranked) + 1)]
    scores = [c.score for c in ranked if c.accepted]
    assert scores == sorted(scores, reverse=True)
    assert all(c.accepted for c in ranked[: len(scores)])


def test_cardinality_and_score_rules() -> None:
    unique = JoinCandidate(
        from_="a.x",
        to="b.y",
        inclusion_ratio=1.0,
        target_uniqueness=1.0,
        source_uniqueness=0.2,
        target_distinct=1000,
        name_similarity=1.0,
    )
    assert cardinality(unique, 0.999) == "N:1"
    unique.cardinality = "N:1"
    assert raw_score(unique, JoinSettings()) == 0.85
    both = unique.model_copy(update={"source_uniqueness": 1.0})
    assert cardinality(both, 0.999) == "1:1"
    many = unique.model_copy(update={"target_uniqueness": 0.5, "cardinality": "N:M"})
    assert cardinality(many, 0.999) == "N:M"
    assert raw_score(many, JoinSettings()) == 0.425
    reverse = unique.model_copy(update={"target_uniqueness": 0.5, "source_uniqueness": 1.0})
    assert cardinality(reverse, 0.999) == "1:N"


def test_pk_to_pk_with_different_names_is_rejected(sap_profile: ProjectProfile) -> None:
    for c in score_candidates(sap_profile, JoinSettings()):
        if c.cardinality == "1:1" and c.name_similarity < 1.0:
            assert not c.accepted
