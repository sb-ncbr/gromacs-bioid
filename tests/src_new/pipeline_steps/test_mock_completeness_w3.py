"""W3/F-N1d: MockAtomGroup completeness for parallel-path PDB generators."""
from __future__ import annotations

import numpy as np
import pytest

from src_new.pipeline_steps.workers import MockAtomGroup
from src_new.signatures.snapshot import SegmentSignatureSnapshot
from src_new.signatures.generators.pdb import (
    fragment_to_pdb_direct,
    select_na_backbone_atom,
)
from src_new.signatures.generators.topology_less_pdb import fragment_to_pdb_topology_less


def _mini_na_snapshot() -> SegmentSignatureSnapshot:
    # two-residue NA fragment: DA (C4',P,O3') + DC (C4',P) with simple coordinates
    resids = [1, 1, 1, 2, 2]
    resnames = ["DA", "DA", "DA", "DC", "DC"]
    names = ["C4'", "P", "O3'", "C4'", "P"]
    elements = ["C", "P", "O", "C", "P"]
    positions = [[float(i), float(i) * 0.5, 0.0] for i in range(5)]
    return SegmentSignatureSnapshot(
        segment_name="SYS", atom_indices=list(range(5)), elements=elements,
        names=names, resnames=resnames, resids=resids, segids=["SYS"] * 5,
        masses=[12.0, 31.0, 16.0, 12.0, 31.0], positions=positions,
        bonds=[(0, 1), (1, 2), (2, 3), (3, 4)],
        flags={"is_nucleic": True, "has_positions": True, "has_elements": True,
               "has_unique_names": True, "has_multi_atom_residues": True},
        atom_count=5, residue_count=2, molecule_type="NUCLEIC", instance_id="i1",
        chain_ids=["SYS"], copy_number=1, element_composition={"C": 3, "P": 2, "O": 1},
    )


class TestMockCompleteness:
    def test_atoms_has_resnums(self):
        g = MockAtomGroup(_mini_na_snapshot())
        assert list(g.atoms.resnums) == [1, 1, 1, 2, 2]
        assert list(g.resnums) == [1, 1, 1, 2, 2]

    def test_residues_have_resindex(self):
        g = MockAtomGroup(_mini_na_snapshot())
        assert [r.resindex for r in g.residues] == [0, 1]

    def test_topology_less_pdb_generates(self):
        out = fragment_to_pdb_topology_less(MockAtomGroup(_mini_na_snapshot()))
        assert "ATOM" in out and "END" in out

    def test_na_backbone_selector_path_generates(self):
        g = MockAtomGroup(_mini_na_snapshot())
        out = fragment_to_pdb_direct(g, True, include_bonds=True,
                                     backbone_selector=select_na_backbone_atom)
        lines = [l for l in out.splitlines() if l.startswith("ATOM")]
        # one line per residue (backbone trace), selects C4' both times
        assert len(lines) == 2
        assert all("C4'" in l for l in lines)
