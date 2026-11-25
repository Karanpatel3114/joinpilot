from joinpilot.config import JoinSettings
from joinpilot.joins.candidates import ProfileIndex, generate_candidates
from joinpilot.joins.models import JoinCandidate
from joinpilot.profiling.models import ProjectProfile


def candidates_of(profile: ProjectProfile, settings: JoinSettings) -> list[JoinCandidate]:
    return generate_candidates(ProfileIndex.build(profile, settings), settings)


def test_candidates_come_only_from_profiled_columns(sap_profile: ProjectProfile) -> None:
    index = ProfileIndex.build(sap_profile, JoinSettings())
    candidates = generate_candidates(index, JoinSettings())
    assert candidates
    for c in candidates:
        assert c.from_ in index.columns and c.to in index.columns
        assert c.source_table != c.target_table


def test_true_joins_are_candidates_with_their_evidence(sap_profile: ProjectProfile) -> None:
    by_pair = {(c.from_, c.to): c for c in candidates_of(sap_profile, JoinSettings())}
    bsid = by_pair[("BSID.KUNNR", "KNA1.KUNNR")]
    assert bsid.normalization == "lpad_zeros:10"
    assert bsid.target_uniqueness == 1.0
    assert bsid.name_similarity == 1.0
    ids = set(bsid.evidence_ids)
    assert any(i.startswith("ov_") for i in ids) and any(i.startswith("uk_") for i in ids)
    known = {o.evidence_id for o in sap_profile.overlaps} | {
        k.evidence_id for k in sap_profile.keys
    }
    assert ids <= known


def test_decimal_and_date_columns_never_become_candidates(sap_profile: ProjectProfile) -> None:
    columns = {c.from_ for c in candidates_of(sap_profile, JoinSettings())}
    assert not columns & {"VBAK.NETWR", "VBAP.NETWR", "KNA1.ERDAT", "BSID.DMBTR"}


def test_name_matches_are_candidates_even_without_overlap(sap_profile: ProjectProfile) -> None:
    settings = JoinSettings(candidate_min_inclusion=1.1)
    pairs = {(c.from_, c.to) for c in candidates_of(sap_profile, settings)}
    assert ("VBAK.KUNNR", "KNA1.KUNNR") in pairs
    assert ("VBAK.WAERK", "BSID.WAERS") not in pairs
