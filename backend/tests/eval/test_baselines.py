from eval.baselines import name_only, overlap_only
from joinpilot.profiling.models import ProjectProfile


def test_name_only_finds_same_name_keys_and_guesses_direction(sap_profile: ProjectProfile) -> None:
    pairs = {(e.from_, e.to) for e in name_only(sap_profile)}
    assert ("VBAK.KUNNR", "KNA1.KUNNR") in pairs
    assert ("KNA1.KUNNR", "VBAK.KUNNR") not in pairs
    assert ("VBAP.VBELN", "VBAK.VBELN") in pairs and ("VBAK.VBELN", "VBAP.VBELN") in pairs


def test_overlap_only_uses_value_overlap_and_keeps_decoys(sap_profile: ProjectProfile) -> None:
    edges = overlap_only(sap_profile)
    pairs = {(e.from_, e.to) for e in edges}
    assert ("VBAK.KUNNR", "KNA1.KUNNR") in pairs
    assert ("VBAK.WAERK", "BSID.WAERS") in pairs
    assert all(e.fan_out is False for e in edges)
