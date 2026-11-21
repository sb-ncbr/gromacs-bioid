"""CSV / API answer per molecule = the web application's (best_hit.py)."""
from src_new.api.best_hit import molecule_result


def h(db, ident, conf, verified=True, **kw):
    return {"database": db, "identifier": ident, "ident_type": kw.pop("t", "PDB_ID"),
            "final_confidence": conf, "is_verified": verified, **kw}


def test_best_is_the_most_confident_verified_hit_not_the_first_stored():
    # 3PTB: the stored order put PDB 1AQ7 (81.4) first; the UI shows UniProt P00760 (84.1)
    r = molecule_result([h("pdb", "1AQ7", 81.4), h("uniprot", "P00760", 84.1, t="UNIPROT_ID"),
                         h("pdb", "9ZZZ", 99.0, verified=False)])
    assert (r["database"], r["identifier"], r["confidence"]) == ("UniProt", "P00760", 84.1)
    assert r["state"] == "identified" and r["confidence_label"] == "high"
    assert r["alternatives"] == ["PDB:1AQ7"]


def test_ties_keep_the_stored_order():
    r = molecule_result([h("pdb", "1AAA", 70.0), h("pdb", "2BBB", 70.0)])
    assert r["identifier"] == "1AAA"


def test_states():
    assert molecule_result([])["state"] == "not_identified"
    assert molecule_result([h("pdb", "1AAA", 90.0, verified=False)])["state"] == "not_identified"
    lead = molecule_result([h("pubchem", "5", 42.0, t="PUBCHEM_CID")])
    assert lead["state"] == "lead" and lead["confidence_label"] == "low"
    ion = molecule_result([h("element", "NA", None, t="PUBCHEM_ATOM")])
    assert ion["state"] == "exact" and ion["confidence"] is None
    gt = molecule_result([h("pdb", "1AAA", 60.0, ground_truth_override="x")])
    assert gt["state"] == "exact" and gt["confidence"] is None


def test_pdb_chain_suffix_is_shown_as_the_ui_shows_it():
    assert molecule_result([h("pdb", "4GUX_A", 90.0)])["identifier"] == "4GUX"


# 2026-11-21 (mdval audit item 8b): coarse-grained molecules
from src_new.api.best_hit import coarse_grained_label, coarse_grained_of  # noqa: E402

CG = {"model": "Martini", "residue": "POPE", "by_name": "PE(16:0/18:1(9Z))"}


def test_coarse_grained_with_nothing_verified_is_its_own_state():
    r = molecule_result([h("pubchem", "123", 0.0, verified=False)], CG)
    assert r["state"] == "coarse_grained" and r["state_label"] == "coarse-grained"
    assert r["name"] == "Coarse-grained (Martini POPE)"
    assert r["by_name"] == "PE(16:0/18:1(9Z))"
    assert (r["database"], r["identifier"], r["confidence"], r["alternatives"]) == ("", "", None, [])
    # atomistic molecules keep "not identified"
    assert molecule_result([h("pubchem", "123", 0.0, verified=False)])["state"] == "not_identified"


def test_a_verified_hit_beats_the_coarse_grained_state():
    # a Martini protein keeps its residue names: its sequence BLASTs fine
    r = molecule_result([h("uniprot", "P00760", 84.1, t="UNIPROT_ID")], {"model": "Martini", "residue": ""})
    assert (r["state"], r["identifier"]) == ("identified", "P00760")


def test_coarse_grained_label():
    assert coarse_grained_label({"model": "Martini", "residue": "W"}) == "Coarse-grained (Martini W)"
    assert coarse_grained_label({"model": "", "residue": "DPPC"}) == "Coarse-grained (DPPC)"
    assert coarse_grained_label(None) == "Coarse-grained"


def test_coarse_grained_of_reads_the_molecule_verdict_and_old_runs():
    data = {"data": {"fragments": {"segments": [
        {"segment": "seg_1_POPE", "type": "lipid", "coarse_grained": CG},
        {"segment": "seg_2_X", "type": "small_molecule"}]}}}
    assert coarse_grained_of(data, "seg_1_POPE") == CG
    assert coarse_grained_of(data, "seg_2_X") is None
    # runs before 2026-11-21: run-level verdict + an element-less segment
    old = {"data": {"universe": {
        "repair_report": {"elements_source": "coarse_grained_blank"},
        "segments": {"seg_0_W": {"properties": {"has_elements": False}},
                     "PROA": {"properties": {"has_elements": True}}}}}}
    assert coarse_grained_of(old, "seg_0_W") == {"model": "", "residue": ""}
    assert coarse_grained_of(old, "PROA") is None
    assert coarse_grained_of({"data": {}}, "seg_0_W") is None
