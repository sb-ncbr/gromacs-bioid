"""Wave-7 Phase 3: nucleic FASTA generation tests.

3.1: resname_to_one_letter consults the nucleic normalizer (terminal codes,
     D- prefix) before the legacy tables; unknown -> 'X' unchanged.
3.2: fasta_resname_nucleic fallback re-gate: covers bondless atomistic NA
     (was a coverage hole) WITHOUT double-firing when map-based applies.
3.3: anchor parameterization: protein path byte-identical; NA anchor=None.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")

from src_new.config.loader import SignaturesConfig
from src_new.input.models import InputKind, LoadDecision
from src_new.loader.repair import RepairReport
from src_new.loader.universe_facade import LoadedUniverse
from src_new.molecules.instances import MoleculeInstance
from src_new.signatures.generators.fasta import (
    MapFastaGeneratorNucleotide,
    ResnameFastaGeneratorNucleotide,
    fragment_to_protseq_map_based,
    resname_to_one_letter,
)


class TestResnameToOneLetterWave7:
    @pytest.mark.parametrize("resn,expected", [
        # terminal codes via the normalizer (the Cyt_c canary names)
        ("DA3", "A"), ("DG5", "G"), ("DC3", "C"), ("DT5", "T"),
        ("A3", "A"), ("U5", "U"),
        # table-covered modifieds degrade to 'X' by design (BLAST-side
        # sanitizer turns X into N; emitting a canonical letter for a
        # modified base would corrupt the alphabet)
        ("PSU", "X"), ("H2U", "X"), ("5MC", "X"), ("OMC", "X"),
        # canonical unchanged
        ("A", "A"), ("DA", "A"), ("DT", "T"), ("U", "U"),
        # protein regressions
        ("ALA", "A"), ("GLY", "G"), ("MET", "M"),
        ("sN", "N"), ("sQ", "Q"), ("sE", "E"),
        # unknowns still degrade to X (BLAST sanitizer handles NA side)
        ("XYZ", "X"), ("M8G", "X"),
    ])
    def test_mapping(self, resn, expected):
        assert resname_to_one_letter(resn) == expected


def _mk_universe(resnames, atom_names_per_res, bonds=None, segid="X"):
    atom_resindex, names = [], []
    for i, anames in enumerate(atom_names_per_res):
        atom_resindex.extend([i] * len(anames))
        names.extend(anames)
    n_res = len(resnames)
    u = mda.Universe.empty(len(names), n_residues=n_res, n_segments=1,
                           atom_resindex=atom_resindex, trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
    u.add_TopologyAttr("resnums", list(range(1, n_res + 1)))
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("segids", [segid])
    u.add_TopologyAttr("elements", ["C"] * len(names))
    u.load_new(np.zeros((len(names), 3), dtype=np.float32), format="memory")
    if bonds:
        u.add_TopologyAttr("bonds", bonds)
    return u


def _mk_facade(universe, segid="X"):
    dec = LoadDecision(input_kind=InputKind.GROMACS, selected_strategy="tpr_only",
                       topology_files=[Path("dummy.tpr")])
    facade = LoadedUniverse(universe=universe, decision=dec,
                            repair_report=RepairReport(), results=None)
    fragment = facade.get_fragment(segid)
    instance = MoleculeInstance(instance_id="test", molecule_type=None)
    return facade, fragment, instance


def _chain_bonds(n_res, atoms_per_res, intra_pairs, cross_pair):
    """intra_pairs: [(a,b)] offsets within each residue; cross_pair links residues."""
    bonds = []
    for i in range(n_res):
        off = i * atoms_per_res
        for a, b in intra_pairs:
            bonds.append((off + a, off + b))
        if i > 0:
            a, b = cross_pair
            bonds.append((off + a, (i - 1) * atoms_per_res + b))
    return bonds


class TestResnameFallbackGate:
    """B2: exact complement of the map-based gate; zero double production."""

    DNA_RES = ["DA", "DC", "DG", "DT"]
    DNA_ATOMS = [["P", "O5'", "C5'", "C4'", "C3'", "O3'"]] * 4

    def test_bonded_atomistic_dna_map_only(self):
        bonds = _chain_bonds(4, 6, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)], (0, 5))
        facade, fragment, inst = _mk_facade(
            _mk_universe(self.DNA_RES, self.DNA_ATOMS, bonds=bonds))
        cfg = SignaturesConfig()
        applicable = [
            MapFastaGeneratorNucleotide(cfg)._is_applicable(inst, fragment, facade),
            ResnameFastaGeneratorNucleotide(cfg)._is_applicable(inst, fragment, facade),
        ]
        assert applicable == [True, False]  # exactly one producer, the map

    def test_bondless_atomistic_dna_resname_only(self):
        facade, fragment, inst = _mk_facade(
            _mk_universe(self.DNA_RES, self.DNA_ATOMS, bonds=None))
        cfg = SignaturesConfig()
        applicable = [
            MapFastaGeneratorNucleotide(cfg)._is_applicable(inst, fragment, facade),
            ResnameFastaGeneratorNucleotide(cfg)._is_applicable(inst, fragment, facade),
        ]
        assert applicable == [False, True]  # NEW: was [False, False] before wave-7

    def test_bondless_resname_generates_correct_sequence(self):
        facade, fragment, inst = _mk_facade(
            _mk_universe(self.DNA_RES, self.DNA_ATOMS, bonds=None))
        cfg = SignaturesConfig()
        gen = ResnameFastaGeneratorNucleotide(cfg)
        assert gen._is_applicable(inst, fragment, facade)
        seq = gen._generate(inst, fragment, facade)
        assert seq == "ACGT"  # resid order: DA DC DG DT

    def test_coarse_grained_dna_resname_only(self):
        # single-atom residues (CG): resname fires, map stays off (multi-atom gate)
        facade, fragment, inst = _mk_facade(
            _mk_universe(self.DNA_RES, [["BB"]] * 4, bonds=None))
        cfg = SignaturesConfig()
        applicable = [
            MapFastaGeneratorNucleotide(cfg)._is_applicable(inst, fragment, facade),
            ResnameFastaGeneratorNucleotide(cfg)._is_applicable(inst, fragment, facade),
        ]
        assert applicable == [False, True]


class TestAnchorParameterization:
    """B3: protein path byte-identical; anchor=None safe for NA."""

    PROT_RES = ["MET", "ALA", "GLY"]
    PROT_ATOMS = [["N", "CA", "C", "O"]] * 3
    NA_RES = ["DA", "DC", "DG", "DT"]
    NA_ATOMS = [["P", "O3'"]] * 4

    def _prot_u(self):
        # linear chain: residue i atom 2 (C) bonded to residue i+1 atom 0 (N)
        bonds = _chain_bonds(3, 4, [(0, 1), (1, 2), (2, 3)], (2, 0))
        return _mk_universe(self.PROT_RES, self.PROT_ATOMS, bonds=bonds)

    def _na_u(self):
        bonds = _chain_bonds(4, 2, [(0, 1)], (0, 1))
        return _mk_universe(self.NA_RES, self.NA_ATOMS, bonds=bonds)

    def test_protein_default_equals_explicit_m(self):
        cfg = SignaturesConfig()
        seq_default = fragment_to_protseq_map_based(self._prot_u().atoms, cfg)
        seq_m = fragment_to_protseq_map_based(self._prot_u().atoms, cfg, anchor="M")
        assert seq_default == seq_m
        assert sorted(seq_default) == sorted("MAG")

    def test_nucleic_anchor_none_equals_legacy_behavior(self):
        """Pre-wave-7 the NA anchor set was always empty; None must not change output."""
        cfg = SignaturesConfig()
        seq_none = fragment_to_protseq_map_based(self._na_u().atoms, cfg, anchor=None)
        seq_legacy = fragment_to_protseq_map_based(self._na_u().atoms, cfg)  # anchor="M", dead for NA
        assert seq_none == seq_legacy
        assert seq_none in {"ACGT", "TGCA"}  # strand orientation is unconstrained
