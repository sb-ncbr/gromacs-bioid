"""Unit tests for src_new.loader.metal_scan (F19).

Synthetic-universe coverage per the approved design:
  * zinc-finger-class orphan Zn -> bound
  * Mg-ATP site -> associated (non-water, non-protein partners)
  * free Cl + bound Zn mix -> both visible; Cl presence-only (no context rec)
  * protein-only negative -> empty presence
  * bound Ca vs passing water Ca discrimination
  * degrades: no positions, no elements attr, context cap exceeded
  * salt box (500 Na + 500 Cl) stays presence-only (no tree, no context recs)
  * vocab filtering (non-channel elements excluded)
  * newly_visible computation against instance-visible elements
  * partner records capped at 8 and distance-sorted
"""
from __future__ import annotations

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")

from src_new.loader.metal_scan import (  # noqa: E402
    ION_CHANNEL_VOCAB, scan_metals,
)


def _universe(residues, trajectory=True, with_elements=True):
    """residues: list of (resname, [(x, y, z, element), ...])."""
    atoms_per = [len(atoms) for _, atoms in residues]
    n_atoms = sum(atoms_per)
    resindex = []
    for ri, cnt in enumerate(atoms_per):
        resindex += [ri] * cnt
    u = mda.Universe.empty(n_atoms, n_residues=len(residues), n_segments=1,
                           atom_resindex=resindex, trajectory=trajectory)
    u.add_TopologyAttr("names", [f"AT{i}" for i in range(n_atoms)])
    u.add_TopologyAttr("resids", list(range(1, len(residues) + 1)))
    u.add_TopologyAttr("resnames", [rn for rn, _ in residues])
    u.add_TopologyAttr("segids", ["A"])
    if with_elements:
        u.add_TopologyAttr("elements",
                           [el for _, atoms in residues for (*_, el) in atoms])
    if trajectory:
        pos = np.array([[x, y, z] for _, atoms in residues
                        for (x, y, z, _) in atoms], dtype=np.float32)
        u.load_new(pos, format="memory")
    return u


def _ala(at=(0.0, 0.0, 0.0)):
    x, y, z = at
    return ("ALA", [(x, y, z, "N"), (x + 1.4, y, z, "C"),
                    (x + 2.0, y + 1.2, z, "C"), (x + 2.8, y, z, "O")])


# ------------------------------------------------------------------ basics

class TestPresenceChannel:
    def test_zinc_finger_bound(self):
        # HIS residues coordinating a single-atom ZN at ~2.3 A  (4341-class)
        residues = [
            _ala((0.0, 0.0, 0.0)),
            ("HIE", [(2.1, 0.5, 0.0, "N"), (3.0, 1.0, 0.0, "C"),
                     (3.5, 2.0, 0.0, "N")]),
            ("HIE", [(5.0, -0.4, 1.0, "N"), (6.0, -0.6, 1.5, "C")]),
            ("ZN", [(4.2, 0.0, 0.0, "Zn")]),
            ("HOH", [(30.0, 30.0, 30.0, "O"), (30.5, 30.5, 30.0, "H")]),
        ]
        out = scan_metals(_universe(residues))
        assert out["present_elements"] == ["Zn"]
        assert out["element_atom_counts"] == {"Zn": 1}
        assert out["context"]["computed"] is True
        assert out["context"]["transition_atom_count"] == 1
        (zn,) = out["atoms"]
        assert zn["element"] == "Zn"
        assert zn["resname"] == "ZN"
        assert zn["single_atom_residue"] is True
        assert zn["coordination"] == "bound"
        kinds = {p["kind"] for p in zn["partners"]}
        assert "protein" in kinds
        assert any(p["resname"] == "HIE" for p in zn["partners"])

    def test_protein_only_negative(self):
        residues = [_ala((0, 0, 0)), _ala((10, 0, 0)), ("HOH", [(5, 5, 5, "O")])]
        out = scan_metals(_universe(residues))
        assert out["present_elements"] == []
        assert out["element_atom_counts"] == {}
        assert out["atoms"] == []
        assert out["context"]["computed"] is True
        assert out["context"]["transition_atom_count"] == 0

    def test_mg_atp_associated(self):
        residues = [
            ("ATP", [(0.0, 0.0, 0.0, "O"), (1.2, 0.5, 0.0, "P"),
                     (2.0, 1.0, 1.0, "O")]),
            ("MG", [(1.0, 0.7, 0.4, "Mg")]),
        ]
        out = scan_metals(_universe(residues))
        (mg,) = out["atoms"]
        assert mg["coordination"] == "associated"
        assert all(p["kind"] == "other" for p in mg["partners"])

    def test_free_cl_and_bound_zn_mix(self):
        residues = [
            _ala((0, 0, 0)),
            ("ZN", [(1.5, 0.5, 0.2, "Zn")]),
            ("CL", [(50.0, 50.0, 50.0, "Cl")]),
            ("HOH", [(50.9, 50.9, 50.0, "O")]),
        ]
        out = scan_metals(_universe(residues))
        assert set(out["present_elements"]) == {"Zn", "Cl"}
        # halides are presence-only: no per-atom context record
        assert [a["element"] for a in out["atoms"]] == ["Zn"]
        assert out["atoms"][0]["coordination"] == "bound"

    def test_ca_bound_vs_passing(self):
        residues = [
            _ala((0, 0, 0)),
            ("CA", [(1.6, 0.4, 0.0, "Ca")]),          # protein-adjacent
            ("HOH", [(40.0, 40.0, 40.0, "O")]),
            ("HOH", [(42.0, 40.5, 40.0, "O")]),
            ("CA", [(41.0, 40.2, 40.0, "Ca")]),        # water-borne
        ]
        out = scan_metals(_universe(residues))
        assert out["element_atom_counts"] == {"Ca": 2}
        cas = sorted(out["atoms"], key=lambda a: a["coordination"])
        coords = {tuple(sorted(p["resname"] for p in a["partners"])):
                  a["coordination"] for a in cas}
        assert "bound" in coords.values()
        assert "free" in coords.values()

    def test_vocab_filtering(self):
        residues = [("LIG", [(0, 0, 0, "C"), (1.0, 0, 0, "He"),
                             (2.0, 0, 0, "Zn")])]
        out = scan_metals(_universe(residues))
        assert out["present_elements"] == ["Zn"]  # He excluded

    def test_newly_visible_flag(self):
        residues = [_ala((0, 0, 0)), ("ZN", [(3.0, 0.4, 0.0, "Zn")])]
        out = scan_metals(_universe(residues), visible_elements={"C", "H", "N"})
        assert out["newly_visible_elements"] == ["Zn"]
        out2 = scan_metals(_universe(residues),
                           visible_elements={"C", "H", "N", "Zn"})
        assert out2["newly_visible_elements"] == []

    def test_partners_sorted_and_capped(self):
        metals_nb = [("ALA", [(float(k) * 0.3 - 2.0, 0.0, 0.0, "N")])
                     for k in range(12)]            # 12 N atoms near origin
        residues = metals_nb + [("ZN", [(0.0, 0.6, 0.0, "Zn")])]
        out = scan_metals(_universe(residues))
        (zn,) = out["atoms"]
        assert len(zn["partners"]) == 8
        ds = [p["distance_A"] for p in zn["partners"]]
        assert ds == sorted(ds)

    def test_all_32_vocab_symbols_detectable(self):
        residues = [(f"X{i:02d}", [(float(i) * 5, 0, 0, sym)])
                    for i, sym in enumerate(ION_CHANNEL_VOCAB)]
        out = scan_metals(_universe(residues))
        assert set(out["present_elements"]) == set(ION_CHANNEL_VOCAB)


# ------------------------------------------------------------------ degrades

class TestDegrades:
    def test_no_positions(self):
        residues = [_ala((0, 0, 0)), ("ZN", [(1.5, 0.3, 0.0, "Zn")])]
        out = scan_metals(_universe(residues, trajectory=False))
        assert out["present_elements"] == ["Zn"]       # presence survives
        assert out["context"]["computed"] is False
        assert out["context"]["reason"] == "no_positions"
        assert out["atoms"] == []

    def test_no_elements_attr(self):
        u = _universe([("ALA", [(0, 0, 0, "C")])], with_elements=False,
                      trajectory=False)
        out = scan_metals(u)
        assert out["present_elements"] == []
        assert out["context"]["reason"] == "no_elements"

    def test_context_cap_exceeded(self):
        residues = [("ZN", [(float(k) * 10, 0, 0, "Zn")]) for k in range(3)]
        out = scan_metals(_universe(residues), max_context_atoms=2)
        assert out["element_atom_counts"] == {"Zn": 3}  # presence intact
        assert out["context"]["computed"] is False
        assert out["context"]["reason"] == "context_atom_cap_exceeded"
        assert out["atoms"] == []

    def test_salt_box_presence_only(self):
        residues = ([("NA", [(float(i) * 4, 0, 0, "Na")]) for i in range(500)]
                    + [("CL", [(float(i) * 4, 2.0, 0, "Cl")])
                       for i in range(500)])
        import time
        t0 = time.perf_counter()
        out = scan_metals(_universe(residues))
        dt = time.perf_counter() - t0
        assert out["element_atom_counts"] == {"Na": 500, "Cl": 500}
        assert out["atoms"] == []                       # no context queries
        assert out["context"]["computed"] is True
        assert out["context"]["transition_atom_count"] == 0
        assert dt < 1.0                                  # cheap fast path

    def test_hydrogens_ignored_in_partners(self):
        residues = [
            ("ALA", [(0.0, 0.0, 0.0, "N"), (0.7, 0.2, 0.0, "H")]),
            ("ZN", [(1.4, 0.0, 0.0, "Zn")]),
        ]
        out = scan_metals(_universe(residues))
        (zn,) = out["atoms"]
        assert zn["coordination"] == "bound"
        assert all(p["kind"] == "protein" for p in zn["partners"])
        # H neighbor at ~0.75 A must not be listed nor dominate partners
        assert len(zn["partners"]) == 1


# ---------------------------------------------------- store integration

class TestFragmentStoreIntegration:
    def test_fragments_metals_recorded(self, tmp_path):
        import json
        from pathlib import Path

        from src_new.input.discovery import (inspect_directory,
                                             select_best_file_combination)
        from src_new.loader.strategies import load_simulation
        from src_new.loader.repair import TopologyRepair
        from src_new.loader.universe_facade import LoadedUniverse
        from src_new.loader.fragment_store import FragmentStore
        from src_new.config.loader import RunConfig
        from src_new.results.results_manager import ResultsManager

        root = Path("tests/data/14976_a")
        bundle = inspect_directory(root)
        decision = select_best_file_combination(bundle)
        results = ResultsManager(tmp_path / "results.json")
        config = RunConfig()
        config.loader.guess_missing_elements = True
        config.loader.guess_missing_masses = True
        config.loader.guess_missing_bonds = True
        load_result = load_simulation(decision, bundle, config, results)
        assert load_result.success
        repair = TopologyRepair(load_result.universe, config)
        repair_report = repair.run()
        facade = LoadedUniverse(load_result.universe, decision, repair_report,
                                results)
        FragmentStore(facade, results)

        assert results.data_exists("fragments/metals")
        payload = results.get_data("fragments/metals")
        assert payload["schema"] == 1
        assert isinstance(payload["present_elements"], list)
        assert isinstance(payload["atoms"], list)
        # payload must be JSON-serialisable verbatim (results contract)
        json.dumps(payload)
