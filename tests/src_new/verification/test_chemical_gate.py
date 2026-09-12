"""F7 chemical-verification gate tests (skeleton-FP corroboration). No network."""

from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from unittest.mock import MagicMock, patch

import pytest

from src_new.config.loader import RunConfig
from src_new.verification.manager import VerificationManager
from src_new.verification.models import CHEMICAL_IDENT_TYPES, SKELF_VERIFY_THRESHOLD
from src_new.signatures.skeletize import format_signature, from_smiles


ETHANOL_SIG = format_signature(from_smiles("CCO"))            # molecule as simulated
PROPANOL_SMILES = "CCCO"                                       # candidate: close but wrong
ETHANOL_SMILES = "CCO"                                         # candidate: correct


def _mk_results(seg="L", skel_sig=ETHANOL_SIG):
    results = MagicMock()

    def get_data(path, default=None):
        if path == "identifiers":
            return {seg: {}}
        if path == f"signatures/{seg}/generated/skeleton_fp":
            return skel_sig
        return default
    results.get_data.side_effect = get_data
    results.data_exists.side_effect = lambda p: p == f"identifiers/{seg}"
    return results


def _mk_manager():
    cfg = MagicMock(spec=RunConfig)
    vc = MagicMock()
    vc.verify_top_n = 25
    vc.resolver_weight = 0.4
    vc.similarity_weight = 0.3
    vc.annotation_weight = 0.3
    vc.min_final_confidence = 30.0
    cfg.verification = vc
    reg = MagicMock()
    reg.get_fetcher.return_value = MagicMock()
    reg.get_applicable_workers.return_value = []
    reg.get_scorer.return_value = None
    return VerificationManager(cfg, registry=reg), reg


HIT_GROUP = {
    "signature": "C25H18N4O5",
    "signature_type": "molecular_formula",
    "consensus_score": 80.0,
    "source_resolvers": ["formula_pubchem"],
    "hit_type": "identity",      # identity free-pass would previously accept this
}


def _collect(hits):
    out = {}
    for h in hits:
        out[(h, "PUBCHEM_CID")] = dict(HIT_GROUP)
    return out


def test_identity_free_pass_dead_for_chemicals_wrong_structure():
    """Formula-identity junk CID must NOT verify even with hit_type identity."""
    mgr, reg = _mk_manager()
    # fetcher returns the WRONG molecule's smiles for this CID
    reg.get_fetcher.return_value.fetch.return_value = PROPANOL_SMILES
    with patch("src_new.verification.manager.collect_hits",
               return_value=[MagicMock()]), \
         patch("src_new.verification.manager.deduplicate_and_score",
               return_value=_collect(["44421909"])):
        per = mgr.verify_all(_mk_results())
    hit = per["L"][0]
    assert hit.is_verified is False
    assert hit.skeleton_sim is not None and hit.skeleton_sim < SKELF_VERIFY_THRESHOLD
    assert "fingerprint" in hit.rejection_reason


def test_correct_structure_verifies():
    """True candidate CID passes the gate via skeleton corroboration."""
    mgr, reg = _mk_manager()
    reg.get_fetcher.return_value.fetch.return_value = ETHANOL_SMILES
    with patch("src_new.verification.manager.collect_hits",
               return_value=[MagicMock()]), \
         patch("src_new.verification.manager.deduplicate_and_score",
               return_value=_collect(["702"])):
        per = mgr.verify_all(_mk_results())
    hit = per["L"][0]
    assert hit.is_verified is True
    assert hit.skeleton_sim == pytest.approx(1.0)
    assert hit.skeleton_method == "skelfp:v1"


def test_missing_molecule_signature_fails_closed():
    """No skeleton_fp on the molecule -> chemical hit cannot verify (honest blind)."""
    mgr, reg = _mk_manager()
    reg.get_fetcher.return_value.fetch.return_value = ETHANOL_SMILES
    with patch("src_new.verification.manager.collect_hits",
               return_value=[MagicMock()]), \
         patch("src_new.verification.manager.deduplicate_and_score",
               return_value=_collect(["702"])):
        per = mgr.verify_all(_mk_results(skel_sig=None))
    hit = per["L"][0]
    assert hit.is_verified is False
    assert hit.rejection_reason == "fingerprint_unavailable"


def test_protein_hits_untouched_by_gate():
    """Non-chemical ident types keep the legacy evidence rule."""
    assert "PDB_ID" not in CHEMICAL_IDENT_TYPES
    assert "UNIPROT_ID" not in CHEMICAL_IDENT_TYPES


def test_prefetch_pubchem_batch_cache(monkeypatch, tmp_path):
    """Batch prefetch fills NFS cache; per-CID fetch then hits cache (no HTTP)."""
    import src_new.verification.fetchers.compound_fetcher as cf
    monkeypatch.setattr(cf, "_SIM_CACHE", str(tmp_path))
    seen = []

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        @property
        def status_code(self): return 200
        def json(self): return self._p

    def fake_get(url):
        seen.append(url)
        return FakeResp({"PropertyTable": {"Properties": [
            {"CID": 1, "CanonicalSMILES": "CCO"},
            {"CID": 2, "CanonicalSMILES": "CCCO"},
        ]}})

    monkeypatch.setattr(cf, "_polite_get", fake_get)
    # bypass cache read (empty tmp dir)
    n = cf.prefetch_pubchem(["1", "2", "1"])
    assert n == 2
    assert len(seen) == 1                      # single CSV call for 3 input ids
    assert cf._cache_read("1") == "CCO"
    assert cf._cache_read("2") == "CCCO"
