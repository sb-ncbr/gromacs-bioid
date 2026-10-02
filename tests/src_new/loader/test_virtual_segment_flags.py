"""Regression test (WAVE-7 refactor fallout): virtual-minority-segment
SegmentProperties must carry a flags DICT.

_compute_flags() returns (flags_dict, na_meta) since the WAVE-7 signature
change; the main-segment branch unpacks it, the virtual-minority branch
(props.flags = self._compute_flags(...)) did not — so any *extract*
against a virtual segment crashed with
    AttributeError: 'tuple' object has no attribute 'get'
First seen fleet-side by the F19 replay runner on __vN-shaped boxes; A/B
checked pre-existing on master (same class as the test_fragment_store /
test_universe_facade failures).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")

from src_new.input.models import InputKind, LoadDecision  # noqa: E402
from src_new.loader.repair import RepairReport  # noqa: E402
from src_new.loader.universe_facade import LoadedUniverse  # noqa: E402


def _mk_universe_with_minority():
    """One segid 'SYS': 2 ALA residues (one bonded 8-atom fragment) +
    2 copies of a 4-atom LIG (bonded) + 2 waters. Virtual discovery must
    expose SYS__v1 for the LIG species."""
    resnames = ["ALA", "ALA", "LIG", "LIG", "HOH", "HOH"]
    atom_names = [
        ["N", "CA", "C", "O"], ["N", "CA", "C", "O"],      # protein chain
        ["C1", "C2", "N1", "O1"], ["C1", "C2", "N1", "O1"],  # ligand copies
        ["O"], ["O"],                                        # waters (skipped)
    ]
    elements = [
        "N", "C", "C", "O", "N", "C", "C", "O",
        "C", "C", "N", "O", "C", "C", "N", "O",
        "O", "O",
    ]
    atom_resindex, names = [], []
    for i, anames in enumerate(atom_names):
        atom_resindex.extend([i] * len(anames))
        names.extend(anames)
    n_atoms = len(names)
    u = mda.Universe.empty(n_atoms, n_residues=len(resnames), n_segments=1,
                           atom_resindex=atom_resindex, trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resids", list(range(1, len(resnames) + 1)))
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("segids", ["SYS"])
    u.add_TopologyAttr("elements", elements)
    pos = np.zeros((n_atoms, 3), dtype=np.float32)
    pos[:, 0] = np.arange(n_atoms) * 3.5
    u.load_new(pos, format="memory")
    # bonds: protein chain (0-3, 4-7, 3-4); ligands (8-11), (12-15); waters none
    bonds = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7),
             (8, 9), (9, 10), (10, 11), (12, 13), (13, 14), (14, 15)]
    u.add_TopologyAttr("bonds", bonds)
    return u


def _mk_facade(u=None):
    u = u if u is not None else _mk_universe_with_minority()
    return LoadedUniverse(
        universe=u,
        decision=LoadDecision(input_kind=InputKind.GROMACS,
                              selected_strategy="tpr_only",
                              topology_files=[Path("dummy.tpr")]),
        repair_report=RepairReport(),
        results=None,
    )


class TestVirtualSegmentFlags:
    def test_virtual_segment_exposed(self):
        facade = _mk_facade()
        assert "SYS__v1" in facade.get_segments()

    def test_virtual_props_flags_is_dict(self):
        facade = _mk_facade()
        props = facade.get_segment_properties("SYS__v1")
        assert isinstance(props.flags, dict), (
            f"flags is {type(props.flags).__name__}, expected dict "
            "(WAVE-7 tuple-unpack regression)")

    def test_extract_molecule_instance_on_virtual_segment(self):
        facade = _mk_facade()
        inst = facade.extract_molecule_instance("SYS__v1")  # no raise
        assert inst is not None
        assert inst.atom_count == 4
