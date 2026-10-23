"""Red-team batch-4 (5.10) — D-10 rerank batch-resolve, network-free.

D-10: the F14 skeleton rerank fetched every chemical candidate serially
(fetcher.fetch: mirror-hit ~ms, mirror-miss 0.34-30+ s PUG/IDSM) for up to
25,000 candidates — enough to consume the whole stage budget after which
D-04 empties the segment. And the computed skel values were recomputed in
the main loop.

Fix pins:
  - mirror bulk resolution (chunked SQL IN) for all CID candidates; ZERO
    network calls in the rerank (misses keep their consensus slot);
  - wall cap = min(config cap, budget fraction of remaining), partial
    progress kept with a recorded reason;
  - rerank's skel/t2 values are reused by the main loop (no recompute).
"""

from __future__ import annotations

import sqlite3
import time

import pytest


def _mk_mirror(tmp_path, rows):
    from src_new.molecules.pubchem_db import PubChemDB
    db_path = tmp_path / "mirror.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE compounds (cid INTEGER PRIMARY KEY, smiles TEXT,"
                 " inchikey TEXT, formula_hill TEXT, exact_mass REAL)")
    conn.executemany("INSERT INTO compounds VALUES (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return PubChemDB(db_path)


class TestByCidsBulk:
    def test_chunked_in_query_matches_by_cid(self, tmp_path):
        rows = [(i, f"C{i}", f"KEY{i}", f"C{i}", float(i)) for i in range(1, 1201)]
        db = _mk_mirror(tmp_path, rows)
        out = db.by_cids([str(i) for i in range(1, 1201)])
        assert len(out) == 1200
        assert out["1"].smiles == "C1"
        assert out["1200"].smiles == "C1200"
        # parity with the single-row accessor on a sample
        assert out["777"].cid == db.by_cid(777).cid

    def test_missing_cids_simply_absent(self, tmp_path):
        db = _mk_mirror(tmp_path, [(1, "C", "K", "C1", 12.0)])
        out = db.by_cids(["1", "999", "abc", ""])
        assert list(out) == ["1"]

    def test_resolve_cids_offline_helper(self, tmp_path):
        from unittest.mock import patch
        from src_new.verification.fetchers import compound_fetcher
        db = _mk_mirror(tmp_path, [(962, "O", "WATERKEY", "H2O", 18.0)])
        with patch.object(compound_fetcher, "_local_db", return_value=db):
            got = compound_fetcher.resolve_cids_offline(["962", "1"])
        assert got == {"962": "O"}

    def test_resolve_cids_offline_no_mirror(self):
        from unittest.mock import patch
        from src_new.verification.fetchers import compound_fetcher
        with patch.object(compound_fetcher, "_local_db", return_value=None):
            assert compound_fetcher.resolve_cids_offline(["962"]) == {}


class TestRerankOfflineAndWallCap:
    def _mk(self, results, top_n=100, cap_s=30.0, fraction=0.2):
        from types import SimpleNamespace
        from src_new.verification.manager import VerificationManager
        from src_new.config.loader import RunConfig

        mgr = VerificationManager.__new__(VerificationManager)
        vc = RunConfig().verification
        vc.verify_top_n = top_n
        vc.verify_rerank_wall_cap_s = cap_s
        vc.verify_rerank_budget_fraction = fraction
        mgr._verification_config = vc
        mgr._registry = SimpleNamespace(
            get_fetcher=lambda *a, **k: None,
            get_applicable_workers=lambda *a, **k: [],
            get_scorer=lambda *a, **k: None)
        return mgr

    def _seed(self, results, n_cids=200):
        from src_new.signatures.skeletize import from_smiles, skeleton_fp, fp_to_hex
        for i in range(n_cids):
            results.set_data(f"identifiers/SEG1/genA/res{i}", {
                "signature": "H2O", "hit_type": "identity",
                "hits": [str(1000 + i)], "ident_type": "PUBCHEM_CID",
                "signature_type": "molecular_formula"})
        results.set_data("signatures/SEG1/generated/smiles", "O")
        results.set_data("signatures/SEG1/generated/skeleton_fp",
                         f"skelfp:v1:{fp_to_hex(skeleton_fp(from_smiles('O')))}")

    def _groups(self, n=200):
        return [
            ((str(1000 + i), "PUBCHEM_CID"),
             {"consensus_score": 100.0, "signature": "H2O",
              "signature_type": "molecular_formula",
              "member_signatures": [("H2O", "molecular_formula")],
              "source_resolvers": ["formula_pubchem"],
              "hit_type": "candidate", "belief": 20.0,
              "n_identity_sources": 0, "n_candidate_sources": 1,
              "n_similarity_sources": 0})
            for i in range(n)
        ]

    def test_mirror_resolved_promoted_network_free(self, tmp_path):
        """Mirror-resolved exact-structure candidates rerank above the
        flood; NO fetcher is consulted in the rerank (network-free, D-10)."""
        from unittest.mock import patch, Mock
        from src_new.results.results_manager import ResultsManager

        results = ResultsManager(tmp_path / "results.json")
        self._seed(results, 0)
        mgr = self._mk(results, top_n=5)
        # registry.get_fetcher must never be used by the rerank
        mgr._registry.get_fetcher = Mock(
            side_effect=AssertionError("network in rerank (D-10)"))
        resolve = lambda cids: {"1000": "O"} if "1000" in cids else {}
        with patch("src_new.verification.manager.resolve_cids_offline",
                   side_effect=resolve):
            out, skel_map, t2_map, stats = mgr._maybe_structure_rerank(
                results, "SEG1", self._groups(), 5,
                lambda: False, lambda: 300.0)
        assert stats["reason"] == "ok"
        assert stats["n_resolved"] == 1
        chem_ids = [k[0] for k, _m in out[:5] if k[1] == "PUBCHEM_CID"]
        assert chem_ids[0] == "1000"
        assert skel_map[("1000", "PUBCHEM_CID")] == pytest.approx(1.0, abs=1e-9)
        assert t2_map[("1000", "PUBCHEM_CID")] == pytest.approx(1.0, abs=1e-9)
        # unresolved candidates keep their values as None (consensus slot)
        assert skel_map[("1001", "PUBCHEM_CID")] is None

    def test_wall_cap_zero_keeps_consensus_order(self, tmp_path):
        from unittest.mock import patch
        from src_new.results.results_manager import ResultsManager

        results = ResultsManager(tmp_path / "results.json")
        self._seed(results, 0)
        mgr = self._mk(results, top_n=5, cap_s=0.0)
        resolve_calls = []
        def resolve(cids):
            resolve_calls.append(cids)
            return {"1000": "O"}
        groups = self._groups()
        with patch("src_new.verification.manager.resolve_cids_offline",
                   side_effect=resolve):
            out, skel_map, t2_map, stats = mgr._maybe_structure_rerank(
                results, "SEG1", groups, 5, lambda: False,
                lambda: 300.0)
        assert out == groups
        assert stats["reason"] == "wall_cap_exceeded"
        assert resolve_calls == []  # cap hit before resolution ran

    def test_rerank_stats_persisted_via_verify_all(self, tmp_path):
        from unittest.mock import patch
        from src_new.results.results_manager import ResultsManager

        results = ResultsManager(tmp_path / "results.json")
        self._seed(results, 200)
        mgr = self._mk(results, top_n=5)
        with patch("src_new.verification.manager.resolve_cids_offline",
                   side_effect=lambda cids: {"1000": "O"}):
            mgr.verify_all(results, deadline_epoch=time.time() + 300)
        stats = results.get_data("verification/SEG1/rerank")
        assert stats is not None, "rerank stats not persisted"
        assert stats["reason"] == "ok"
        assert stats["n_candidates"] == 200
        assert stats["n_resolved"] == 1

    def test_resolved_values_reused_by_main_loop(self, tmp_path):
        """The rerank's skeleton tanimoto must not be recomputed in the
        candidate loop."""
        from unittest.mock import patch
        from src_new.results.results_manager import ResultsManager
        from src_new.verification import manager as mgr_mod

        results = ResultsManager(tmp_path / "results.json")
        self._seed(results, 200)
        mgr = self._mk(results)
        calls = []
        orig = mgr_mod._chemical_corroboration
        def spy(*a, **k):
            calls.append(a)
            return orig(*a, **k)
        # every candidate resolves offline -> the candidate loop reuses the
        # rerank's measurements exclusively
        with patch("src_new.verification.manager.resolve_cids_offline",
                   side_effect=lambda cids: {c: "O" for c in cids}), \
             patch.object(mgr_mod, "_chemical_corroboration", side_effect=spy):
            mgr.verify_all(results, deadline_epoch=time.time() + 300)
        stats = results.get_data("verification/SEG1/rerank")
        assert stats["n_resolved"] == 200
        hits = results.get_data("verification/SEG1/verified_hits")
        hit0 = hits[0]
        assert hit0["skeleton_sim"] == pytest.approx(1.0, abs=1e-9)
        assert calls == [], f"corroboration recomputed: {len(calls)} calls"
