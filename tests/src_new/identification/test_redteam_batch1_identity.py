"""Red-team Batch 1.4 (identity semantics) regression tests.

  C-01: RCSB Search `score` is rank-normalized (top hit ALWAYS 1.0, last 0.5).
        pdb_struct derived `hit_type: identity` from score*100 >= 99.9, so the
        rank-1 entry became a "verified identity" for EVERY query — even for
        proteins with no PDB structure (live probe: Q5VSL9 -> '7WO9' identity).
  C-02: AlphaFind identity = aligned_percentage >= 99.5, but that is COVERAGE,
        not identity. Every well-folded ortholog qualifies (up to 50 false
        "identity" ALPHAFOLD_IDs; each carries identity belief).
  C-17: IDSM/ChEMBL identity = Tanimoto 1.0, which lumps stereoisomers,
        isotopologues, tautomers and charge forms (L-alanine probe: 141 PubChem
        CIDs returned as "identity").
"""
from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig


class TestC01RcsbIdentityFromRank:
    def test_rank_normalized_score_never_yields_identity(self, monkeypatch):
        """Live-probe shape (Q5VSL9, AF model query): rank-1 '7WO9' scores
        1.0 purely by normalization — there is no true identity."""
        from src_new.identification.resolvers.pdb_struct import PDBStructResolverProtein

        r = PDBStructResolverProtein(RunConfig())
        monkeypatch.setattr(
            r, "_pdb_fetch_similar_structures",
            lambda pdb_path, deployment_file_access: [("7WO9", 100.0), ("4IFQ", 62.51)],
        )
        identical = r._pdb_fetch_identical_structures("x.pdb", False)
        assert identical == [], (
            "rank-normalized RCSB score must not mint identity hits (C-01) — "
            "identity needs an absolute measure, not rank-1-always-1.0"
        )


class TestC02AlphaFindIdentityRule:
    """Response shapes from the live AlphaFind probes (audit appendix C)."""

    def _resolver(self, monkeypatch, entries):
        from src_new.identification.resolvers.alphafind import AlphaFindStructResolver

        r = AlphaFindStructResolver(RunConfig())
        monkeypatch.setattr(r, "_alphafind_fetch_response",
                            lambda p: {"digest": "Q", "search_time": 1,
                                       "results": entries})
        return r

    def test_coverage_is_not_identity(self, monkeypatch):
        r = self._resolver(monkeypatch, [
            # well-folded ortholog: full coverage, mediocre TM — NOT identity
            {"object_id": "AF-ORTHO", "aligned_percentage": 100.0,
             "tm_score": 0.97, "sequence_aligned_percentage": 98.5},
            # true match
            {"object_id": "AF-TRUE", "aligned_percentage": 100.0,
             "tm_score": 0.995, "sequence_aligned_percentage": 100.0},
        ])
        identical = r._alphafind_identity("x.pdb")
        assert identical == ["AF-TRUE"], (
            f"aligned_percentage (coverage) mints false identities (C-02): {identical!r}"
        )

    def test_missing_tm_fields_mean_not_identity(self, monkeypatch):
        """Conservative: without the absolute measures we cannot claim identity."""
        r = self._resolver(monkeypatch, [
            {"object_id": "AF-NOFIELDS", "aligned_percentage": 100.0},
        ])
        assert r._alphafind_identity("x.pdb") == []

    def test_similarity_score_is_tm_based(self, monkeypatch):
        r = self._resolver(monkeypatch, [
            {"object_id": "AF-ORTHO", "aligned_percentage": 100.0,
             "tm_score": 0.97, "sequence_aligned_percentage": 98.5},
        ])
        sim = dict(r._alphafind_similarity("x.pdb"))
        assert sim.get("AF-ORTHO") == pytest.approx(97.0), (
            "similarity score must be TM-score x100, not coverage (C-02)"
        )


class TestC17TanimotoIsSimilarityNotIdentity:
    def test_idsm_identity_channel_dropped(self, monkeypatch):
        import src_new.identification.resolvers.idsm as idsm
        from src_new.identification.resolvers.idsm import IDSMResolverPubchem

        # L-alanine probe shape: stereo/isotopic variants at Tanimoto 1.0
        monkeypatch.setattr(idsm, "idsm_fetch_similarity_match",
                            lambda *a, **k: ["5460975", "16213291"])
        r = IDSMResolverPubchem(RunConfig())
        out = r._resolve_identity("CC(=O)Oc1ccccc1C(=O)O", "")
        assert out == [], (
            "Tanimoto 1.0 lumps stereo/isotopologues — not identity (C-17); "
            "such hits belong to similarity with score 100"
        )

    def test_chembl_identity_channel_dropped(self, monkeypatch):
        import src_new.identification.resolvers.chembl as chembl
        from src_new.identification.resolvers.chembl import ChemblResolver

        monkeypatch.setattr(chembl, "chembl_fetch_similarity_match",
                            lambda *a, **k: ["25", "131987"])
        r = ChemblResolver(RunConfig())
        assert r._resolve_identity("CC(=O)Oc1ccccc1C(=O)O", "") == [], (
            "Tanimoto 1.0 is not identity (C-17)"
        )
