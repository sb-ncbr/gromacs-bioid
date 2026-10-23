"""Red-team batch-4 (5.6) — D-03 verify window per ident-family.

D-03: the verification window is one consensus-sorted cut, ties broken by
insertion order. A PDB flood (probe d_p6: 150 identical lysozyme chains,
all consensus 100) filled 100/100 slots and UniProt P00698 — the only
protein-family record — was never verified at all.

Fix pins:
  - groups are interleaved by ident FAMILY (pdb / uniprot-pool incl.
    SWISSPROT / alphafold / ncbi / chemical / other), one per family in
    rotation, before the top-N cut;
  - within a family the consensus order is preserved;
  - `verification/<seg>/window` persists {n_groups, n_window,
    n_dropped_by_type} additively.
"""

from __future__ import annotations

import pytest

from src_new.verification.manager import _family_interleave, _ident_family


def _group(identifier, ident_type, consensus=100.0):
    return ((identifier, ident_type),
            {"consensus_score": consensus,
             "signature": "X", "signature_type": "residue_sequence_protein"})


class TestIdentFamily:
    def test_family_mapping(self):
        assert _ident_family("PDB_ID") == "pdb"
        assert _ident_family("UNIPROT_ID") == "uniprot"
        assert _ident_family("SWISSPROT_ID") == "uniprot"
        assert _ident_family("ALPHAFOLD_ID") == "alphafold"
        assert _ident_family("NR_ID") == "ncbi"
        assert _ident_family("NT_ID") == "ncbi"
        assert _ident_family("PUBCHEM_CID") == "chemical"
        assert _ident_family("ELEMENT") == "other"
        assert _ident_family("LM_ID") == "chemical"


class TestFamilyInterleave:
    def test_pdb_flood_cannot_hide_uniprot(self):
        """d_p6 reconstruction: 150 PDB chains + P00698 -> P00698 IS in the
        window (pre-fix: 100/100 PDB)."""
        groups = [_group(f"1L{i:02d}", "PDB_ID") for i in range(150)]
        groups.append(_group("P00698", "UNIPROT_ID"))
        window, stats = _family_interleave(groups, 100)
        ids = [k[0] for k, _m in window]
        assert "P00698" in ids
        per_family = {}
        for (iid, it), _m in window:
            per_family[it] = per_family.get(it, 0) + 1
        # 1 uniprot + 99 pdb
        assert per_family == {"PDB_ID": 99, "UNIPROT_ID": 1}
        assert stats["n_groups"] == 151
        assert stats["n_window"] == 100
        assert stats["n_dropped_by_type"] == {"pdb": 51}

    def test_three_families_rotate(self):
        groups = ([_group(f"PB{i}", "PDB_ID") for i in range(10)]
                  + [_group(f"UP{i}", "UNIPROT_ID") for i in range(5)]
                  + [_group(f"CH{i}", "PUBCHEM_CID") for i in range(4)])
        window, stats = _family_interleave(groups, 9)
        ids = [k[0] for k, _m in window]
        # rotation order follows first appearance: pdb, uniprot, chemical
        assert ids[:9] == ["PB0", "UP0", "CH0", "PB1", "UP1", "CH1",
                           "PB2", "UP2", "CH2"]
        assert stats["n_window"] == 9

    def test_family_supply_exhaustion_fills_from_others(self):
        groups = ([_group(f"PB{i}", "PDB_ID") for i in range(3)]
                  + [_group(f"UP{i}", "UNIPROT_ID") for i in range(20)])
        window, _ = _family_interleave(groups, 5)
        ids = [k[0] for k, _m in window]
        assert ids == ["PB0", "UP0", "PB1", "UP1", "PB2"]

    def test_single_family_unchanged_order(self):
        groups = [_group(f"PB{i:03d}", "PDB_ID", consensus=float(100 - i))
                  for i in range(20)]
        window, _ = _family_interleave(groups, 5)
        ids = [k[0] for k, _m in window]
        assert ids == ["PB000", "PB001", "PB002", "PB003", "PB004"]


class TestWindowPersisted:
    def test_window_stats_stored(self, tmp_path):
        """Manager persists verification/<seg>/window additively and P00698
        survives the flood end-to-end."""
        import time
        from types import SimpleNamespace
        from src_new.results.results_manager import ResultsManager
        from src_new.verification.manager import VerificationManager
        from src_new.config.loader import RunConfig

        mgr = VerificationManager.__new__(VerificationManager)
        mgr._registry = SimpleNamespace(
            get_fetcher=lambda ident_type, signature_type=None: None,
            get_applicable_workers=lambda *a, **k: [],
            get_scorer=lambda *a, **k: None,
        )
        mgr._verification_config = RunConfig().verification

        results = ResultsManager(tmp_path / "results.json")
        for i in range(150):
            results.set_data(f"identifiers/SEG1/genA/res{i}", {
                "signature": "MKVL", "hit_type": "identity",
                "hits": [f"1L{i:03d}"], "ident_type": "PDB_ID",
                "signature_type": "residue_sequence_protein"})
        results.set_data("identifiers/SEG1/genB/resUp", {
            "signature": "MKVL", "hit_type": "identity",
            "hits": ["P00698"], "ident_type": "UNIPROT_ID",
            "signature_type": "residue_sequence_protein"})

        mgr.verify_all(results, deadline_epoch=time.time() + 300)
        stats = results.get_data("verification/SEG1/window")
        assert stats is not None, "window stats not persisted"
        assert stats["n_groups"] == 151
        assert stats["n_window"] == 100
        assert stats["n_dropped_by_type"].get("pdb") == 51

        stored = results.get_data("verification/SEG1/verified_hits")
        ids = {h["identifier"] for h in stored}
        assert "P00698" in ids
