"""Tests for G9 per-segment selectors into the system mmCIF.

BACKEND_GAPS G9: the /render payload must carry, per segment, a selector
usable in the system mmCIF. The export writes ``_atom_site.id = universe
atom.index`` and ``auth_asym_id = atom.segid`` (verified here against a
real exported file), so atom-index ranges are exact even for virtual
minority segments whose atoms interleave with their siblings'.
"""

from types import SimpleNamespace

import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")
pytest.importorskip("Bio.PDB")
import numpy as np

from src_new.loader.export_mmcif import (
    _indices_to_ranges,
    _segment_selectors,
    export_system_mmcif,
)


def _tiny_universe():
    """3 atoms / 2 residues / 2 segments: atoms 0-1 seg A, atom 2 seg B."""
    u = MDAnalysis.Universe.empty(
        n_atoms=3, n_residues=2, atom_resindex=[0, 0, 1],
        n_segments=2, residue_segindex=[0, 1], trajectory=True,
    )
    u.add_TopologyAttr("segids", ["A", "B"])
    u.add_TopologyAttr("resids", [1, 2])
    u.add_TopologyAttr("resnames", ["GLY", "HOH"])
    u.add_TopologyAttr("names", ["CA", "O", "H1"])
    u.atoms.positions = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0],
                                  [5.0, 0.0, 0.0]])
    return u


class _RecordingResults:
    """ResultsManager stand-in: records set_data/add_artifact calls."""

    def __init__(self):
        self.data = {}
        self.artifacts = []

    def set_data(self, key, value):
        self.data[key] = value

    def add_artifact(self, *args, **kwargs):
        self.artifacts.append((args, kwargs))


class TestIndicesToRanges:
    def test_contiguous(self):
        assert _indices_to_ranges([0, 1, 2]) == [[0, 3]]

    def test_broken_runs(self):
        assert _indices_to_ranges([0, 1, 5, 9, 10]) == [[0, 2], [5, 6], [9, 11]]

    def test_single(self):
        assert _indices_to_ranges([7]) == [[7, 8]]


class TestSegmentSelectors:
    def test_real_segments(self):
        u = _tiny_universe()
        facade = SimpleNamespace(universe=u, get_segments=lambda: {"A", "B"})
        sel = _segment_selectors(facade)
        assert sel["A"] == {"chains": ["A"], "atom_index_ranges": [[0, 2]],
                            "atom_count": 2}
        assert sel["B"] == {"chains": ["B"], "atom_index_ranges": [[2, 3]],
                            "atom_count": 1}

    def test_interleaved_segids_remap_to_file_rows(self):
        """Chain-grouped write order breaks universe-index contiguity:
        atoms of seg A at universe indices 0 and 2 (B at 1) land at file
        rows 0 and 1 — row ranges, not universe ranges, are the contract."""
        u = MDAnalysis.Universe.empty(
            n_atoms=3, n_residues=3, atom_resindex=[0, 1, 2],
            n_segments=2, residue_segindex=[0, 1, 0], trajectory=True,
        )
        u.add_TopologyAttr("segids", ["A", "B"])
        u.add_TopologyAttr("resids", [1, 2, 3])
        u.add_TopologyAttr("resnames", ["GLY", "HOH", "ALA"])
        u.add_TopologyAttr("names", ["CA", "O", "CB"])
        facade = SimpleNamespace(universe=u, get_segments=lambda: {"A", "B"})
        sel = _segment_selectors(facade)
        # universe indices of A are [0, 2] (non-contiguous); file rows
        # (chain A written first, then B) are [0, 1] (contiguous)
        assert sel["A"]["atom_index_ranges"] == [[0, 2]]
        assert sel["A"]["atom_count"] == 2
        assert sel["B"]["atom_index_ranges"] == [[2, 3]]

    def test_normal_segment_selector_uses_fragment_not_whole_segid(self):
        """W3 A2/B4 (BH-002): when a segid holds several species (chain +
        a stray single-atom ion), the CHAIN's selector must cover only its
        own fragment's rows — the virtual sibling's atom must not overlap
        (cytc: HEM Fe atom 1676 became B__v1 inside seg B)."""
        u = _tiny_universe()  # A: atoms 0-1, B: atom 2
        chain = SimpleNamespace(indices=np.array([0]), segids=np.array(["A"]))
        virt = SimpleNamespace(indices=np.array([1]), segids=np.array(["A"]))
        frags = {"A": SimpleNamespace(atoms=chain),
                 "A__v1": SimpleNamespace(atoms=virt),
                 "B": None}
        facade = SimpleNamespace(
            universe=u,
            get_segments=lambda: {"A", "A__v1", "B"},
            get_fragment=lambda name: frags.get(name),
        )
        sel = _segment_selectors(facade)
        assert sel["A"]["atom_index_ranges"] == [[0, 1]], sel["A"]
        assert sel["A__v1"]["atom_index_ranges"] == [[1, 2]]
        a_rows = set(range(sel["A"]["atom_index_ranges"][0][0],
                           sel["A"]["atom_index_ranges"][0][1]))
        v_rows = set(range(sel["A__v1"]["atom_index_ranges"][0][0],
                           sel["A__v1"]["atom_index_ranges"][0][1]))
        assert not (a_rows & v_rows)

    def test_virtual_segment_uses_parent_chain_and_exact_ranges(self):
        """A virtual species (interleaved with its sibling) carries the
        parent segid in the file; only atom ranges isolate it."""
        u = _tiny_universe()
        virt_atoms = SimpleNamespace(indices=np.array([0, 2]),
                                     segids=np.array(["A", "A"]))
        facade = SimpleNamespace(
            universe=u,
            get_segments=lambda: {"A", "A__v1"},
            get_fragment=lambda name: SimpleNamespace(atoms=virt_atoms) if name == "A__v1" else None,
        )
        sel = _segment_selectors(facade)
        assert sel["A__v1"]["chains"] == ["A"]  # parent chain in the file
        # universe atoms 0 (row 0, seg A) and 2 (row 2, seg B): both rows
        # are named, so the select spans [0,1) and [2,3)
        assert sel["A__v1"]["atom_index_ranges"] == [[0, 1], [2, 3]]
        assert sel["A__v1"]["atom_count"] == 2

    def test_export_persists_selectors_and_file_ids_match(self, tmp_path):
        """End-of-export proof: results carry render/segment_selectors and
        the written atom_site loop matches the row contract — ids are
        1-based row numbers in chain-grouped write order."""
        u = _tiny_universe()
        facade = SimpleNamespace(universe=u, get_segments=lambda: {"A", "B"})
        results = _RecordingResults()
        out = tmp_path / "system.mmcif"

        export_system_mmcif(facade, out, results)

        sel = results.data["render/segment_selectors"]
        assert set(sel) == {"A", "B"}
        assert sel["A"]["atom_index_ranges"] == [[0, 2]]
        assert sel["B"]["atom_index_ranges"] == [[2, 3]]

        # Empirical invariant: parse the atom_site loop. _atom_site.id is
        # the 1-based row number (MMCIFIO renumbers; preserve_atom_numbering
        # is not used), so row p (0-based) has id p+1 and the chain column
        # of every row in a segment's ranges is one of its chains.
        lines = out.read_text().splitlines()
        col_names = []
        atom_rows = []
        in_loop = False
        for line in lines:
            if line.startswith("_atom_site."):
                col_names.append(line.split()[0])
                in_loop = True
            elif in_loop and line.startswith(("ATOM", "HETATM")):
                atom_rows.append(line.split())
        id_col = col_names.index("_atom_site.id")
        asym_col = col_names.index("_atom_site.auth_asym_id")
        assert [int(r[id_col]) for r in atom_rows] == [1, 2, 3]
        for seg, entry in sel.items():
            for start, end in entry["atom_index_ranges"]:
                for row_idx in range(start, end):
                    assert int(atom_rows[row_idx][id_col]) == row_idx + 1
                    assert atom_rows[row_idx][asym_col] in entry["chains"]
