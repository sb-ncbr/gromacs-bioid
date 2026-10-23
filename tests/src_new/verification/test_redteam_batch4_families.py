"""Red-team batch-4 (5.9) — D-08 evidence-family belief + C-09b candidate demotion.

D-08: belief counts distinct RESOLVER NAMES, so a formula flood (6 PubChem-
family chains on one CID) reaches B=98 while a perfectly cross-validated
UniProt hit caps at ~60. The chains are not independent: formula_pubchem +
formula_pubchem_local + formula_hfamily are one source (PubChem formula
index); inchikey_pubchem + inchikey_self one; blast_uniprot +
blast_swissprot_protein one. And UNIPROT_ID / SWISSPROT_ID rows for the
same accession split into never-pooled groups.

C-09b: identity asserted ONLY by formula/candidate-list chains is a
CANDIDATE assertion — it must not verify, must not outrank true identity,
and counts as its own (formula) family in the belief.

Scope decisions (pre-flagged): per-class C normalization stays OFF behind
the `belief_source_normalize` flag (G-A/F-track decides activation);
NR/NT unchanged (no scorers; C-10 lands in TASK 6).
"""

from __future__ import annotations

import pytest

from src_new.verification.dedup import (
    RawHit, deduplicate_and_score, resolver_belief, RESOLVER_SOURCES,
)


def _rh(identifier, ident_type, resolver, sig="X", stype="resname",
        hit_type="identity", score=100.0):
    return RawHit(identifier, ident_type, resolver, score, sig, stype, hit_type)


class TestEvidenceFamilyCounting:
    def test_formula_flood_counts_once(self):
        """TOCL2 reconstruction: 7 resolvers, 3 evidence families
        (pubchem-structure, inchikey, pubchem-formula); the formula family
        counts κ-weighted (candidate), not as identity (C-09b)."""
        resolvers = ["pubchem_struct", "idsm_pubchem", "inchikey_pubchem",
                     "inchikey_self", "formula_pubchem",
                     "formula_pubchem_local", "formula_hfamily"]
        out = deduplicate_and_score(
            [_rh("5459377", "PUBCHEM_CID", r) for r in resolvers])
        meta = out[("5459377", "PUBCHEM_CID")]
        assert meta["n_identity_chains"] == 7      # resolver count kept
        assert meta["n_identity_sources"] == 2     # structure + inchikey
        assert meta["n_candidate_sources"] == 1    # the ONE formula family
        assert meta["belief"] == pytest.approx(resolver_belief(2, 1))

    def test_unknown_resolver_is_its_own_family(self):
        out = deduplicate_and_score([
            _rh("1", "LM_ID", "some_custom_tool"),
            _rh("1", "LM_ID", "another_custom_tool")])
        meta = out[("1", "LM_ID")]
        assert meta["n_identity_sources"] == 2  # no accidental collapse

    def test_swissprot_uniprot_blasts_share_one_family(self):
        out = deduplicate_and_score([
            _rh("P00698", "UNIPROT_ID", "blast_uniprot",
                sig="MKVL", stype="residue_sequence_protein"),
            _rh("P00698", "SWISSPROT_ID", "blast_swissprot_protein",
                sig="MKVL", stype="residue_sequence_protein")])
        # pooled by accession under the UNIPROT-family group key
        assert ("P00698", "UNIPROT_ID") in out
        assert ("P00698", "SWISSPROT_ID") not in out
        meta = out[("P00698", "UNIPROT_ID")]
        assert meta["n_identity_sources"] == 1
        assert meta["source_resolvers"] == ["blast_swissprot_protein",
                                            "blast_uniprot"] or \
               meta["source_resolvers"] == ["blast_uniprot",
                                            "blast_swissprot_protein"]
        assert meta["belief"] == pytest.approx(50.0)

    def test_distinct_accessions_stay_separate(self):
        out = deduplicate_and_score([
            _rh("P00698", "UNIPROT_ID", "blast_uniprot",
                stype="residue_sequence_protein"),
            _rh("Q99999", "UNIPROT_ID", "blast_uniprot",
                stype="residue_sequence_protein")])
        assert ("P00698", "UNIPROT_ID") in out
        assert ("Q99999", "UNIPROT_ID") in out


class TestCandidateDemotion:
    def test_formula_only_identity_demotes_to_candidate(self):
        out = deduplicate_and_score(
            [_rh("5151", "PUBCHEM_CID", "formula_pubchem"),
             _rh("5151", "PUBCHEM_CID", "formula_hfamily")])
        meta = out[("5151", "PUBCHEM_CID")]
        assert meta["hit_type"] == "candidate"
        assert meta["n_identity_sources"] == 0
        assert meta["n_candidate_sources"] == 1

    def test_mixed_identity_stays_identity(self):
        out = deduplicate_and_score(
            [_rh("5151", "PUBCHEM_CID", "formula_pubchem"),
             _rh("5151", "PUBCHEM_CID", "inchikey_self")])
        meta = out[("5151", "PUBCHEM_CID")]
        assert meta["hit_type"] == "identity"


class TestManagerFlow:
    def _mgr(self, worker=None):
        from types import SimpleNamespace
        from src_new.verification.manager import VerificationManager
        from src_new.config.loader import RunConfig

        mgr = VerificationManager.__new__(VerificationManager)
        mgr._registry = SimpleNamespace(
            get_fetcher=lambda ident_type, signature_type=None: SimpleNamespace(
                supports=lambda _it: True, fetch=lambda _nid, _it: "O"),
            get_applicable_workers=lambda st, it: [worker] if worker else [],
            get_scorer=lambda *a, **k: None)
        mgr._verification_config = RunConfig().verification
        return mgr

    def _seed(self, results, entries):
        for i, e in enumerate(entries):
            results.set_data(f"identifiers/SEG1/genA/res{i}", e)
        results.set_data("signatures/SEG1/generated/smiles", "O")
        from src_new.signatures.skeletize import from_smiles, skeleton_fp, fp_to_hex
        results.set_data("signatures/SEG1/generated/skeleton_fp",
                         f"skelfp:v1:{fp_to_hex(skeleton_fp(from_smiles('O')))}")

    def test_candidate_demoted_end_to_end(self, tmp_path):
        """Seed a formula-only group via the dedup path: collect_hits takes
        the resolver name from the path key ('res<i>' here), so this path
        cannot exercise the family map. Instead pin the manager's contract:
        hit_type == 'candidate' from metadata must not act as identity."""
        import time
        from unittest.mock import patch, MagicMock
        from src_new.results.results_manager import ResultsManager
        from src_new.verification.dedup import RawHit, deduplicate_and_score

        groups = deduplicate_and_score(
            [_rh("962", "PUBCHEM_CID", "formula_pubchem")])
        mgr = self._mgr()
        results = ResultsManager(tmp_path / "results.json")
        self._seed(results, [{
            "signature": "H2O", "hit_type": "identity", "hits": ["962"],
            "ident_type": "PUBCHEM_CID", "signature_type": "molecular_formula"}])
        with patch("src_new.verification.manager.collect_hits",
                   return_value=[MagicMock()]), \
             patch("src_new.verification.manager.deduplicate_and_score",
                   return_value=groups):
            mgr.verify_all(results, deadline_epoch=time.time() + 60)
        stored = results.get_data("verification/SEG1/verified_hits")[0]
        assert stored["hit_type"] == "candidate"
        # the F7 skeleton gate owns the chemical verdict — the candidate
        # verifies BY STRUCTURE (skel 1.0), never by the assertion, and its
        # belief is the κ-weighted candidate-chain value, not identity's
        assert stored["is_verified"] is True
        assert stored["belief"] == pytest.approx(resolver_belief(0, 1))


class TestBeliefNormalizeFlag:
    def test_flag_off_by_default(self):
        from src_new.config.loader import RunConfig
        assert RunConfig().verification.belief_source_normalize is False

    def test_normalize_when_enabled(self):
        from src_new.verification.manager import _normalize_family_belief
        # chemical class: 3 families seen of 5 possible -> 60
        assert _normalize_family_belief(3, "chemical") == pytest.approx(60.0)
        assert _normalize_family_belief(1, "uniprot") == pytest.approx(50.0)
        assert _normalize_family_belief(5, "chemical") == pytest.approx(100.0)
