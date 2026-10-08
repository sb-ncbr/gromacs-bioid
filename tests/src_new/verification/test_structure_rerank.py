"""F14 skeleton-aware chemical candidate rerank tests (audit 2026-09-26, WAVE 5).

Covers the pure ordering helper (_structure_rerank_groups) and the manager
integration (_maybe_structure_rerank). No network; structures come from a
stub fetcher.
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from types import SimpleNamespace
from unittest.mock import Mock

from src_new.signatures.skeletize import (
    from_smiles, skeleton_fp, fp_to_hex,
)
from src_new.verification.manager import (
    VerificationManager, _structure_rerank_groups, _molecule_skeleton_fp_hex,
)
from src_new.verification.models import SKELF_VERIFY_THRESHOLD


BENZENE = "c1ccccc1"
PHENOL = "Oc1ccccc1"
HEXANE = "CCCCCC"


def _hex(smiles):
    return fp_to_hex(skeleton_fp(from_smiles(smiles)))


def _group(cid, ident_type, consensus):
    return ((cid, ident_type), {"consensus_score": consensus})


class TestOrderingHelper:
    """Pure ordering semantics of _structure_rerank_groups."""

    def test_inert_below_threshold_preserves_legacy_exactly(self):
        groups = [
            _group("962", "PUBCHEM_CID", 100.0),
            _group("1ABC", "PDB_ID", 95.0),
            _group("702", "PUBCHEM_CID", 100.0),
        ]
        skel_map = {("962", "PUBCHEM_CID"): 0.2, ("702", "PUBCHEM_CID"): 0.19}
        out = _structure_rerank_groups(groups, skel_map, SKELF_VERIFY_THRESHOLD)
        assert [g[0][0] for g in out] == ["962", "1ABC", "702"]

    def test_reranks_chem_only_and_preserves_nonchem_positions(self):
        groups = [
            _group("JUNK1", "PUBCHEM_CID", 100.0),
            _group("1ABC", "PDB_ID", 95.0),
            _group("GOOD", "PUBCHEM_CID", 50.0),
            _group("P12345", "UNIPROT_ID", 90.0),
            _group("JUNK2", "PUBCHEM_CID", 100.0),
        ]
        skel_map = {
            ("JUNK1", "PUBCHEM_CID"): 0.15,
            ("GOOD", "PUBCHEM_CID"): 0.99,
            ("JUNK2", "PUBCHEM_CID"): 0.10,
        }
        out = _structure_rerank_groups(groups, skel_map, SKELF_VERIFY_THRESHOLD)
        ids = [g[0][0] for g in out]
        assert ids[1] == "1ABC"        # non-chem positions untouched
        assert ids[3] == "P12345"
        chem_ids = [i for i in ids if i not in ("1ABC", "P12345")]
        assert chem_ids == ["GOOD", "JUNK1", "JUNK2"]   # skel desc, consensus tiebreak

    def test_none_fetch_scores_zero_and_sinks(self):
        groups = [
            _group("NOFETCH", "PUBCHEM_CID", 100.0),
            _group("GOOD", "PUBCHEM_CID", 50.0),
        ]
        skel_map = {("NOFETCH", "PUBCHEM_CID"): None, ("GOOD", "PUBCHEM_CID"): 0.85}
        out = _structure_rerank_groups(groups, skel_map, SKELF_VERIFY_THRESHOLD)
        assert [g[0][0] for g in out] == ["GOOD", "NOFETCH"]

    def test_consensus_tiebreak_within_equal_skels(self):
        groups = [
            _group("A", "PUBCHEM_CID", 60.0),
            _group("B", "PUBCHEM_CID", 90.0),
            _group("C", "PUBCHEM_CID", 70.0),
        ]
        skel_map = {
            ("A", "PUBCHEM_CID"): 0.9, ("B", "PUBCHEM_CID"): 0.8, ("C", "PUBCHEM_CID"): 0.8,
        }
        out = _structure_rerank_groups(groups, skel_map, SKELF_VERIFY_THRESHOLD)
        assert [g[0][0] for g in out] == ["A", "B", "C"]


def _manager_with(skel_hex, fetcher, max_cands=25000):
    mgr = VerificationManager.__new__(VerificationManager)
    registry = Mock()
    registry.get_fetcher = lambda ident_type: fetcher
    mgr._registry = registry
    mgr._verification_config = SimpleNamespace(
        verify_rerank_max_candidates=max_cands)
    results = Mock()
    mol_v = f"skelfp:v1:{skel_hex}|C6H6" if skel_hex else ""
    results.get_data = lambda path: mol_v if "skeleton_fp" in path else None
    return mgr, results


class _StubFetcher:
    def __init__(self, smiles_by_id):
        self._m = smiles_by_id
        self.calls = []

    def fetch(self, identifier, ident_type):
        self.calls.append(identifier)
        return self._m.get(identifier)


class TestManagerRerank:
    def _groups(self, junk_n, add_good=True):
        gs = [_group(f"J{i}", "PUBCHEM_CID", 100.0) for i in range(junk_n)]
        if add_good:
            gs.insert(1, _group("962", "PUBCHEM_CID", 50.0))
        return sorted(gs, key=lambda x: -x[1]["consensus_score"])

    def test_promotes_correct_isomer_into_window(self):
        fetcher = _StubFetcher({"962": BENZENE, **{f"J{i}": HEXANE for i in range(5)}})
        mgr, results = _manager_with(_hex(BENZENE), fetcher)
        groups = self._groups(5)
        top_n = 3
        out = mgr._maybe_structure_rerank(results, "B", groups, top_n, lambda: False)
        # benzene-exact candidate must climb to the first chemical slot
        chem_ids = [g[0][0] for g in out[:top_n] if g[0][1] == "PUBCHEM_CID"]
        assert chem_ids[0] == "962"

    def test_window_fits_short_circuits_without_fetches(self):
        fetcher = _StubFetcher({})
        mgr, results = _manager_with(_hex(BENZENE), fetcher)
        groups = self._groups(2)
        out = mgr._maybe_structure_rerank(results, "B", groups, 100, lambda: False)
        assert out == groups
        assert fetcher.calls == []

    def test_no_molecule_skeleton_short_circuits(self):
        fetcher = _StubFetcher({})
        mgr, results = _manager_with("", fetcher)
        groups = self._groups(5)
        out = mgr._maybe_structure_rerank(results, "B", groups, 3, lambda: False)
        assert out == groups
        assert fetcher.calls == []

    def test_raise_only_when_nothing_reaches_threshold(self):
        fetcher = _StubFetcher({"962": HEXANE, **{f"J{i}": HEXANE for i in range(4)}})
        mgr, results = _manager_with(_hex(BENZENE), fetcher)
        groups = self._groups(4)
        out = mgr._maybe_structure_rerank(results, "B", groups, 3, lambda: False)
        assert out == groups

    def test_candidate_cap_falls_back_to_legacy(self):
        fetcher = _StubFetcher({f"J{i}": BENZENE for i in range(4)} | {"962": BENZENE})
        mgr, results = _manager_with(_hex(BENZENE), fetcher, max_cands=3)
        groups = self._groups(4)
        out = mgr._maybe_structure_rerank(results, "B", groups, 3, lambda: False)
        assert out == groups
        assert fetcher.calls == []

    def test_budget_exceeded_falls_back_to_legacy(self):
        fetcher = _StubFetcher({"962": BENZENE, **{f"J{i}": HEXANE for i in range(4)}})
        mgr, results = _manager_with(_hex(BENZENE), fetcher)
        groups = self._groups(4)
        out = mgr._maybe_structure_rerank(results, "B", groups, 3, lambda: True)
        assert out == groups


def _vh(identifier, ident_type, conf, verified=True, skel=None, ev=1):
    """VerifiedHit-shaped test double (only fields the ordering touches)."""
    return SimpleNamespace(
        identifier=identifier, ident_type=ident_type,
        final_confidence=conf, is_verified=verified, skeleton_sim=skel,
        supporting_evidence_count=ev,
    )


class TestFidelityOrderHits:
    """F16 presentation ordering: _fidelity_order_hits / _fidelity_order_key.

    Projection-proven target numbers (rerank_projection.json): fidelity-first
    lifts inchikey validated@5/@10 to 82.5/88.5 (gate 0.7). These tests only
    pin the deterministic mechanics behind that projection.
    """

    def test_verified_chem_block_sorted_by_skeleton_desc(self):
        from src_new.verification.manager import _fidelity_order_hits
        hits = [
            _vh("CID_LOW", "PUBCHEM_CID", 99.0, skel=0.71),
            _vh("1ABC", "PDB_ID", 88.0),
            _vh("CID_GT", "PUBCHEM_CID", 40.0, skel=1.0),
            _vh("CID_MID", "PUBCHEM_CID", 90.0, skel=0.85),
        ]
        out = _fidelity_order_hits(hits)
        assert [h.identifier for h in out] == ["CID_GT", "CID_MID", "CID_LOW", "1ABC"]

    def test_unverified_chem_stays_block2_original_order(self):
        from src_new.verification.manager import _fidelity_order_hits
        hits = [
            _vh("REJ1", "PUBCHEM_CID", 95.0, verified=False, skel=0.99),
            _vh("1ABC", "PDB_ID", 88.0),
            _vh("CID_OK", "PUBCHEM_CID", 50.0, skel=0.80),
        ]
        out = _fidelity_order_hits(hits)
        # verified chem first; then ORIGINAL relative order of the rest,
        # even though REJ1 has a higher skeleton_sim and confidence
        assert [h.identifier for h in out] == ["CID_OK", "REJ1", "1ABC"]

    def test_tie_break_chain_conf_then_identifier_then_type(self):
        from src_new.verification.manager import _fidelity_order_hits
        hits = [
            _vh("ZZZ", "PUBCHEM_CID", 90.0, skel=0.9),
            _vh("AAA", "PUBCHEM_CID", 90.0, skel=0.9),   # tie on skel+conf -> id asc
            _vh("MMM", "PUBCHEM_CID", 95.0, skel=0.9),   # higher conf first
            _vh("AAA", "INCHIKEY", 90.0, skel=0.9),      # same id -> type asc
        ]
        out = _fidelity_order_hits(hits)
        assert [(h.identifier, h.ident_type) for h in out] == [
            ("MMM", "PUBCHEM_CID"),
            ("AAA", "INCHIKEY"),
            ("AAA", "PUBCHEM_CID"),
            ("ZZZ", "PUBCHEM_CID"),
        ]

    def test_tie_break_prefers_evidence_count_over_plateau_confidence(self):
        """A6 (2026-10-08): within a same-skeleton plateau, pubchem-family
        final_confidence is F-07 ordinal-stub quantized -- it must NOT
        arbitrage rank between skeleton-equal candidates. supporting
        evidence count (distinct resolvers that found the hit) is the real
        corroboration signal and ranks BEFORE final_confidence. Residual
        ~223-case rerank cohort (F-7 heal line) was plateau-lottery losses.
        """
        from src_new.verification.manager import _fidelity_order_hits
        hits = [
            _vh("AAA_PLATEAU", "PUBCHEM_CID", 95.0, skel=1.0, ev=1),
            _vh("ZZZ_EVIDENCE", "PUBCHEM_CID", 60.0, skel=1.0, ev=4),
            _vh("MMM_MID", "PUBCHEM_CID", 95.0, skel=1.0, ev=2),
        ]
        out = _fidelity_order_hits(hits)
        assert [h.identifier for h in out] == ["ZZZ_EVIDENCE", "MMM_MID", "AAA_PLATEAU"]

    def test_tie_break_equal_evidence_falls_back_to_confidence(self):
        """A6 is a strict chain extension: equal evidence counts preserve the
        old behavior byte-identically (confidence desc -> id -> type)."""
        from src_new.verification.manager import _fidelity_order_hits
        hits = [
            _vh("ZZZ", "PUBCHEM_CID", 90.0, skel=1.0, ev=2),
            _vh("AAA", "PUBCHEM_CID", 95.0, skel=1.0, ev=2),
        ]
        out = _fidelity_order_hits(hits)
        assert [h.identifier for h in out] == ["AAA", "ZZZ"]

    def test_nan_and_none_skeleton_sink_to_block1_bottom(self):
        import math
        from src_new.verification.manager import _fidelity_order_hits
        hits = [
            _vh("NAN", "PUBCHEM_CID", 99.0, skel=float("nan")),
            _vh("NONE", "PUBCHEM_CID", 98.0, skel=None),
            _vh("INF", "PUBCHEM_CID", 97.0, skel=math.inf),
            _vh("OK", "PUBCHEM_CID", 1.0, skel=0.72),
        ]
        out = _fidelity_order_hits(hits)
        assert out[0].identifier == "OK"

    def test_idempotent(self):
        from src_new.verification.manager import _fidelity_order_hits
        hits = [
            _vh("B", "PUBCHEM_CID", 90.0, skel=0.8),
            _vh("A", "PUBCHEM_CID", 90.0, skel=0.8),
            _vh("P", "PDB_ID", 70.0),
            _vh("C", "PUBCHEM_CID", 10.0, verified=False, skel=0.9),
        ]
        once = _fidelity_order_hits(hits)
        twice = _fidelity_order_hits(once)
        assert [h.identifier for h in once] == [h.identifier for h in twice]

    def test_no_verified_chem_returns_copy_same_order(self):
        from src_new.verification.manager import _fidelity_order_hits
        hits = [_vh("1ABC", "PDB_ID", 88.0), _vh("P12345", "UNIPROT_ID", 70.0)]
        out = _fidelity_order_hits(hits)
        assert [h.identifier for h in out] == ["1ABC", "P12345"]
        assert out is not hits
