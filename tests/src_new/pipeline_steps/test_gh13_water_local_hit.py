"""GitHub #13: water segments are never resolved, and always get one local
identity hit (PubChem 962) — also when other segments are duplicates.

Live evidence (NMRlipids 777, run 4d35e6bb): two identical K+ segments made
member_to_rep non-empty, the A7 filter then dropped seg_2_TIP3 and water came
back 'not identified'; in all-unique systems water was instead resolved in
full (137 chemical candidates).
"""
from __future__ import annotations

import pytest

pytest.importorskip("MDAnalysis")
pytest.importorskip("rdkit")

from tests.src_new.pipeline_steps.test_identify_grouping_a7 import (  # noqa: E402
    _ctx, _ion_sigs, _run_identify, _small_sigs)


def _water_sigs(resname: str = "TIP3") -> dict:
    return {"generated": {"smiles": "O", "inchi_key": "XLYOFNOQVPJJNP-UHFFFAOYSA-N",
                          "molecular_formula": "H2O", "resname": resname,
                          "name_molecule": "water"}}


def _assert_water_hit(results, seg):
    rec = results.get_data(f"identifiers/{seg}/smiles/water_local")
    assert rec["hits"] == ["962"]
    assert rec["ident_type"] == "PUBCHEM_CID" and rec["hit_type"] == "identity"
    assert rec["signature_type"] == "smiles"


def test_water_kept_when_other_segments_are_duplicates(tmp_path):
    sigs = {"seg_3_POT": _ion_sigs("K"), "seg_5_POT": _ion_sigs("K"),
            "seg_0_POPC": _small_sigs("WTJKGGKOPKCXLL-VYOBOKEXSA-N"),
            "seg_2_TIP3": _water_sigs()}
    ctx, results, _ = _ctx(tmp_path, sigs)
    resolved = {c for inst in _run_identify(ctx) for c in inst.calls}
    assert "seg_2_TIP3" not in resolved
    assert resolved == {"seg_0_POPC", "seg_3_POT"}
    _assert_water_hit(results, "seg_2_TIP3")


def test_water_not_resolved_in_all_unique_system(tmp_path):
    sigs = {"seg_0_DOPC": _small_sigs("SNKAWJBJQDLSFF-NVKMUCNASA-N"),
            "seg_3_SOL": _water_sigs("SOL")}
    ctx, results, _ = _ctx(tmp_path, sigs)
    resolved = {c for inst in _run_identify(ctx) for c in inst.calls}
    assert resolved == {"seg_0_DOPC"}
    _assert_water_hit(results, "seg_3_SOL")


def test_water_only_system(tmp_path):
    ctx, results, _ = _ctx(tmp_path, {"W": _water_sigs()})
    assert not {c for inst in _run_identify(ctx) for c in inst.calls}
    _assert_water_hit(results, "W")
