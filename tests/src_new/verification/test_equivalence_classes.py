"""Tests for v3.142 Phase 4: equivalence class ids + per-segment class sizes."""
from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from unittest.mock import MagicMock, patch

from src_new.config.loader import RunConfig
from src_new.signatures.skeletize import format_signature, from_smiles, fp_to_hex, parse_signature, skeleton_fp
from src_new.verification.manager import VerificationManager, _equivalence_class_id
from src_new.verification.models import VerificationScore


# --- helpers (mirrors test_water_ground_truth.py) ----------------------------

def _mk_manager():
    cfg = MagicMock(spec=RunConfig)
    vc = MagicMock()
    vc.verify_top_n = 25
    vc.resolver_weight = 0.4
    vc.similarity_weight = 0.4
    vc.annotation_weight = 0.2
    vc.min_final_confidence = 30.0
    cfg.verification = vc
    reg = MagicMock()
    fetcher = MagicMock()
    # real SMILES so skeleton fps are real: A and B are the SAME molecule
    # across two databases; C is a different molecule (and fails the gate).
    fetcher.fetch.side_effect = {"CID_A": "O", "CHEMBLID_B": "O", "CID_C": "Cl"}.get
    reg.get_fetcher.return_value = fetcher
    worker = MagicMock()
    worker.verify.return_value = VerificationScore(
        kind="similarity", metric_name="idsm", raw_score=1.0, normalized_score=100.0
    )
    reg.get_applicable_workers.return_value = [worker]
    reg.get_scorer.return_value = None
    return VerificationManager(cfg, registry=reg)


def _mk_results(seg="seg_9_TOCL2"):
    results = MagicMock()
    mol_sig = format_signature(from_smiles("O"))  # stored form: "skelfp:v1:<hex>"
    records_calls = []

    def get_data(path, default=None):
        if path == "identifiers":
            return {seg: {}}
        if path == f"signatures/{seg}/generated/skeleton_fp":
            return mol_sig
        if path == f"universe/segments/{seg}/properties":
            return {"atom_count_fragment": 248}
        if path == "fragments/segments":
            return [{"segment": seg, "type": "lipid", "copies": 60, "atoms_per_copy": 248}]
        return default
    results.get_data.side_effect = get_data
    results.data_exists.side_effect = lambda p: p == f"identifiers/{seg}"
    results._set_data_calls = records_calls

    def set_data(path, value):
        records_calls.append((path, value))
    results.set_data.side_effect = set_data
    return results


def _grp(sig="O"):
    return {
        "signature": sig,
        "signature_type": "smiles",
        "consensus_score": 100.0,
        "belief": 50.0,  # v3.142 R-a: one identity chain
        "source_resolvers": ["pubchem_formula"],
        "hit_type": "identity",
    }


def _verify(mgr, results, groups):
    with patch("src_new.verification.manager.collect_hits", return_value=[MagicMock()]), \
         patch("src_new.verification.manager.deduplicate_and_score", return_value=groups):
        return mgr.verify_all(results)


# --- tests (manager-level) ---------------------------------------------------

def test_same_molecule_across_databases_shares_class_id():
    mgr = _mk_manager()
    seg = "seg_9_TOCL2"
    results = _mk_results(seg)
    groups = {
        ("CID_A", "PUBCHEM_CID"): _grp(),
        ("CHEMBLID_B", "CHEMBL_ID"): _grp(),
    }
    hits = _verify(mgr, results, groups)[seg]
    a, b = hits[0], hits[1]
    assert a.is_verified and b.is_verified
    assert a.equivalence_class_id is not None
    assert a.equivalence_class_id == b.equivalence_class_id
    assert a.equivalence_class_id == "skeleton:" + fp_to_hex(skeleton_fp(from_smiles("O")))


def test_different_molecule_gets_different_class_and_sizes_map():
    mgr = _mk_manager()
    seg = "seg_9_TOCL2"
    results = _mk_results(seg)
    groups = {
        ("CID_A", "PUBCHEM_CID"): _grp(),
        ("CHEMBLID_B", "CHEMBL_ID"): _grp(),
        ("CID_C", "PUBCHEM_CID"): _grp(),
    }
    hits = _verify(mgr, results, groups)[seg]
    by_id = {h.identifier: h for h in hits}
    o_class = by_id["CID_A"].equivalence_class_id
    c_class = by_id["CID_C"].equivalence_class_id
    assert by_id["CID_C"].is_verified is False  # Cl != O skeleton
    assert c_class != o_class

    size_calls = [v for (p, v) in results._set_data_calls if p.endswith("/class_sizes")]
    assert size_calls, "class_sizes map must be stored additively per segment"
    sizes = size_calls[-1]
    assert sizes[o_class] == 2      # two verified records, one structure
    assert all(v >= 1 for v in sizes.values())


def test_element_and_fallback_class_ids_are_stable():
    assert _equivalence_class_id("ELEMENT", "Na", "element", None, None) == "element:Na"
    score = VerificationScore(kind="similarity", metric_name="align", raw_score=0.87,
                              normalized_score=87.0)
    # D-06 (red-team batch-4): a score WITHOUT reference content no longer
    # yields a score-bucket class ('align:0.87'); it falls back to the
    # record. Content-keyed donors yield 'seqref:<sha>'.
    assert _equivalence_class_id("UNIPROT_ID", "P12345", "residue_sequence", None, score) == "record:UNIPROT_ID:P12345"
    content_score = VerificationScore(kind="similarity", metric_name="seq_identity_coverage",
                                      raw_score=0.87, normalized_score=87.0,
                                      details={"ref_seq_sha1": "abc123"})
    assert _equivalence_class_id("UNIPROT_ID", "P12345", "residue_sequence", None, content_score) == "seqref:abc123"
    tm = VerificationScore(kind="similarity", metric_name="tm", raw_score=0.77,
                           normalized_score=77.0)
    assert _equivalence_class_id("PDB_ID", "1ABC", "pdb_protein", None, tm) == "record:PDB_ID:1ABC"
    # no proof available -> record-level fallback
    assert _equivalence_class_id("NR_ID", "NP_123", "residue_sequence", None, None) == "record:NR_ID:NP_123"
