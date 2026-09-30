"""Facade-level tests for wave-7 enhanced nucleic acid recognition.

Covers the ``enhanced_nucleic_recognition`` toggle on ``LoadedUniverse``:
- OFF = bit-for-bit legacy (closed 15-code table) behavior
- ON  = tier-1 liberal resname normalization + tier-2 structural probe
        with mandatory cross-residue phosphodiester guard

Synthetic universes only (fast path, no trajectory fixtures).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")

from src_new.input.models import InputKind, LoadDecision
from src_new.loader.repair import RepairReport
from src_new.loader.universe_facade import LoadedUniverse

# Per-residue sugar-phosphate atom set used for tier-2 test residues
# (plus one base atom so HAS_MULTI_ATOM_RESIDUES stays true).
_SUGAR_NAMES = ["P", "O5'", "C5'", "C4'", "C3'", "O3'", "N9", "C8"]


def _mk_decision() -> LoadDecision:
    return LoadDecision(
        input_kind=InputKind.GROMACS,
        selected_strategy="tpr_only",
        topology_files=[Path("dummy.tpr")],
    )


def _mk_universe(resnames, atom_names_per_res, bonds=None, segid="X"):
    """Synthetic universe: explicit per-residue atom names and bonds."""
    atom_resindex, names = [], []
    for i, anames in enumerate(atom_names_per_res):
        atom_resindex.extend([i] * len(anames))
        names.extend(anames)
    n_res = len(resnames)
    u = mda.Universe.empty(len(names), n_residues=n_res, n_segments=1,
                           atom_resindex=atom_resindex, trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("segids", [segid])
    u.load_new(np.zeros((len(names), 3), dtype=np.float32), format="memory")
    if bonds:
        u.add_TopologyAttr("bonds", bonds)
    return u


def _mk_facade(universe, enhanced: bool) -> LoadedUniverse:
    with tempfile.TemporaryDirectory() as tmpdir:
        facade = LoadedUniverse(
            universe=universe,
            decision=_mk_decision(),
            repair_report=RepairReport(),
            results=None,
            enhanced_nucleic_recognition=enhanced,
        )
        props = facade.get_segment_properties("X")
        # keep plain data; facade lifetime ends with tmpdir
        return props.to_dict(), props


def _backbone_bonds(per_res_atoms, p_index=0, o3_index=5):
    """Realistic chain topology: intra-residue backbone bonds
    (P-O5'-C5'-C4'-C3'-O3', indices 0-5) PLUS P(res i) - O3'(res i-1)
    cross-residue phosphodiester bonds. Intra-residue connectivity is
    required so the whole chain forms ONE fragment (as real topologies do).
    """
    bonds = []
    offset = 0
    offsets = []
    for anames in per_res_atoms:
        offsets.append(offset)
        offset += len(anames)
    for i, off in enumerate(offsets):
        # intra-residue backbone chain: 0-1-2-3-4-5
        for j in range(p_index, o3_index):
            bonds.append((off + j, off + j + 1))
        # cross-residue phosphodiester: P(i) - O3'(i-1)
        if i > 0:
            bonds.append((off + p_index, offsets[i - 1] + o3_index))
    return bonds


class TestToggleParity:
    def test_canonical_dna_passes_both_modes(self):
        u = _mk_universe(["DA"] * 8, [["P", "O3'"]] * 8)
        on, _ = _mk_facade(u, True)
        off, _ = _mk_facade(u, False)
        assert on["is_nucleic"] and off["is_nucleic"]
        assert on["na_detection"] == "name"
        assert off["na_detection"] == "legacy_name"

    def test_protein_unaffected_both_modes(self):
        u = _mk_universe(["ALA"] * 8, [["C"]] * 8)
        on, _ = _mk_facade(u, True)
        off, _ = _mk_facade(u, False)
        assert not on["is_nucleic"] and not off["is_nucleic"]


class TestTerminalCodes:
    """8 residues: 5 canonical DA + DA3/DG5/DC3 terminal codes.

    The LIVE legacy table (src.constants, 80 entries) already covers these
    terminal codes, so both modes pass - this is a strict parity check that
    enhanced mode does not change verdicts where legacy already works.
    """

    RESNAMES = ["DA"] * 5 + ["DA3", "DG5", "DC3"]
    ATOMS = [["P", "O3'"]] * 8

    def test_legacy_off_passes_too(self):
        props, _ = _mk_facade(_mk_universe(self.RESNAMES, self.ATOMS), False)
        assert props["is_nucleic"]
        assert props["na_detection"] == "legacy_name"

    def test_enhanced_on_passes(self):
        props, _ = _mk_facade(_mk_universe(self.RESNAMES, self.ATOMS), True)
        assert props["is_nucleic"]
        assert props["na_detection"] == "name"
        assert props["na_structural_promotions"] == 0


class TestModifiedBasesNoRegression:
    """PSU (in the live legacy table) must pass in BOTH modes, including
    bondless input where the tier-2 probe cannot fire. Guards against the
    tier-1-superset regression (enhanced must never drop legacy verdicts)."""

    RESNAMES = ["DA"] * 3 + ["PSU"] * 5
    ATOMS = [["P", "O3'"]] * 8

    def test_bondless_legacy_passes(self):
        props, _ = _mk_facade(_mk_universe(self.RESNAMES, self.ATOMS), False)
        assert props["is_nucleic"]

    def test_bondless_enhanced_passes_via_table_union(self):
        props, _ = _mk_facade(_mk_universe(self.RESNAMES, self.ATOMS), True)
        assert props["is_nucleic"]
        assert props["na_detection"] == "name"
        assert props["na_structural_promotions"] == 0


class TestStructuralProbe:
    """3 DA + 5 M8G (exotic modified name absent from ANY table) with full
    sugar atoms + chain linkage.

    Atom-weighted tier-1: DA 3*8 = 24 of 64 atoms = 0.375 >= probe floor.
    All 5 M8G fingerprint-positive -> promoted -> 64/64 -> nucleic.
    """

    RESNAMES = ["DA"] * 3 + ["M8G"] * 5
    ATOMS = [_SUGAR_NAMES] * 8

    def test_off_mode_never_probes(self):
        props, _ = _mk_facade(
            _mk_universe(self.RESNAMES, self.ATOMS,
                         bonds=_backbone_bonds(self.ATOMS)),
            False)
        assert not props["is_nucleic"]
        assert props["na_detection"] == "none"

    def test_on_mode_promotes_via_structure(self):
        props, _ = _mk_facade(
            _mk_universe(self.RESNAMES, self.ATOMS,
                         bonds=_backbone_bonds(self.ATOMS)),
            True)
        assert props["is_nucleic"]
        assert props["na_detection"] == "structure"
        assert props["na_structural_promotions"] == 1  # one unique resname: M8G

    def test_bondless_cannot_promote(self):
        """Same composition without bonds -> guard fails -> no promotion."""
        props, _ = _mk_facade(_mk_universe(self.RESNAMES, self.ATOMS), True)
        assert not props["is_nucleic"]
        assert props["na_detection"] == "none"

    def test_star_spelling_promotes(self):
        atoms = [[n.replace("'", "*") for n in _SUGAR_NAMES]] * 8
        props, _ = _mk_facade(
            _mk_universe(self.RESNAMES, atoms,
                         bonds=_backbone_bonds(atoms)),
            True)
        assert props["is_nucleic"]
        assert props["na_detection"] == "structure"


class TestCofactorGuard:
    """DA + COA where COA carries full sugar atoms but only intra-res bonds.

    Must NOT classify as nucleic (the CoA 3'-phosphate trap).
    """

    RESNAMES = ["DA"] + ["COA"]
    ATOMS = [_SUGAR_NAMES, _SUGAR_NAMES]

    def test_intra_residue_phosphate_not_promoted(self):
        # intra-residue O3'-P bond inside COA only (atoms 13-8), no chain link
        props, _ = _mk_facade(
            _mk_universe(self.RESNAMES, self.ATOMS, bonds=[(13, 8)]),
            True)
        assert not props["is_nucleic"]
        assert props["na_detection"] == "none"


class TestProbeFloor:
    """Mostly-ligand segment: tier-1 fraction < 0.3 -> probe never runs."""

    def test_low_coverage_not_nucleic(self):
        resnames = ["DA"] + ["LIG"] * 6
        atoms = [_SUGAR_NAMES] + [["C"]] * 6
        props, _ = _mk_facade(_mk_universe(resnames, atoms), True)
        assert not props["is_nucleic"]
        assert props["na_detection"] == "none"
        assert props["na_structural_promotions"] == 0
