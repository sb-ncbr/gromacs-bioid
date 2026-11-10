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
