"""Config-flow E2E for v3.142 Phase 3 (checkpoint 3).

Simulates the run-creation flow the API performs: nested overrides are
applied to a fresh RunConfig (POST /runs config_json path), the config is
written to the run dir as config.ini, read back (rerun path), then
verification runs against a minimal but REAL ResultsManager. Assertions:
raw user weights survive in the ini; verification/_meta records both raw
and normalized-effective weights; the composed confidence respects the
normalized bounds.
"""

from pathlib import Path

from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager
from src_new.verification.manager import VerificationManager

SEG = "seg_6_SOD"

# Mirrors the stored identifier state produced by the atom resolver
# (same payload as test_verify_universe_props.py; verified against live
# run 9d90d777 results.json).
ATOM_IDENTIFIERS_BLOCK = {
    "atom": {
        "atom": {
            "signature": "Na",
            "hit_type": "identity",
            "hits": ["Na"],
            "ident_type": "ELEMENT",
            "signature_type": "element",
        }
    }
}


def _ini_roundtrip_with_overrides(tmp_path: Path, overrides: dict) -> RunConfig:
    """POST /runs override path (apply_nested_overrides) + rerun ini path."""
    cfg = RunConfig()
    cfg.apply_nested_overrides(overrides)
    ini = tmp_path / "config.ini"
    cfg.to_ini_path(ini)
    return RunConfig.from_ini_path(ini)


def _run_verify(tmp_path: Path, cfg: RunConfig):
    rm_path = tmp_path / "results.json"
    rm = ResultsManager(str(rm_path), pipeline_name="test_confidence_meta")
    for key, value in ATOM_IDENTIFIERS_BLOCK.items():
        rm.set_data(f"identifiers/{SEG}/{key}", value)
    manager = VerificationManager(cfg)
    manager.verify_all(rm)
    meta = rm.get_data("verification/_meta")
    hits = rm.get_data(f"verification/{SEG}/verified_hits", [])
    return meta, hits


def test_unnormalized_weights_flow_through_ini_and_are_normalized_at_use(tmp_path):
    cfg = _ini_roundtrip_with_overrides(tmp_path, {
        "verification": {
            "resolver_weight": 0.5,
            "similarity_weight": 0.5,
            "annotation_weight": 0.5,
        }
    })
    # raw user values survive the ini round-trip (provenance of intent)
    assert cfg.verification.resolver_weight == 0.5
    assert cfg.verification.similarity_weight == 0.5
    assert cfg.verification.annotation_weight == 0.5

    meta, hits = _run_verify(tmp_path, cfg)
    assert meta is not None
    assert meta["weights_raw"] == [0.5, 0.5, 0.5]
    assert all(abs(w - 1.0 / 3.0) < 1e-12 for w in meta["weights_effective"])
    assert meta["confidence_formula_version"].startswith("v3.142")
    assert meta["belief_constants"]["rho"] == 0.5
    assert abs(meta["belief_constants"]["kappa"] - 1.0 / 3.0) < 1e-12

    # element hit, 1 identity chain: 1/3*belief(50) + 1/3*match(100) + 1/3*0 = 50
    verified = [h for h in hits if h["is_verified"]]
    assert verified, f"no verified hits in {hits}"
    assert abs(verified[0]["final_confidence"] - 50.0) < 1e-9
    assert verified[0]["final_confidence"] <= 100.0


def test_zero_sum_weights_fall_back_to_equal_thirds(tmp_path):
    cfg = _ini_roundtrip_with_overrides(tmp_path, {
        "verification": {
            "resolver_weight": 0.0,
            "similarity_weight": 0.0,
            "annotation_weight": 0.0,
        }
    })
    meta, hits = _run_verify(tmp_path, cfg)
    assert all(abs(w - 1.0 / 3.0) < 1e-12 for w in meta["weights_effective"])
    verified = [h for h in hits if h["is_verified"]]
    assert abs(verified[0]["final_confidence"] - 50.0) < 1e-9
