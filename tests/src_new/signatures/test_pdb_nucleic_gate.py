"""Wave-7 Phase 4: pdb_nucleic applicability gate widened to atomistic NA.

Previously the nucleic PDB generators required NOT-multi-atom residues
(CG-only), so atomistic DNA/RNA - the common case - never produced PDB
signatures at all. The restriction is now dropped for NA; CG keeps working.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")

from src_new.config.loader import SignaturesConfig
from src_new.input.models import InputKind, LoadDecision
from src_new.loader.repair import RepairReport
from src_new.loader.universe_facade import LoadedUniverse
from src_new.molecules.instances import MoleculeInstance
from src_new.signatures.generators.pdb import (
    PDBBackboneGeneratorNoSanitizeNucleic,
    PDBGeneratorNoSanitizeNucleic,
)


def _mk_universe(resnames, atom_names_per_res, segid="X"):
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
    return u


def _mk_facade(universe, segid="X"):
    dec = LoadDecision(input_kind=InputKind.GROMACS, selected_strategy="tpr_only",
                       topology_files=[Path("dummy.tpr")])
    facade = LoadedUniverse(universe=universe, decision=dec,
                            repair_report=RepairReport(), results=None)
    fragment = facade.get_fragment(segid)
    instance = MoleculeInstance(instance_id="test", molecule_type=None)
    return facade, fragment, instance


class TestNucleicPdbGate:
    DNA_RES = ["DA", "DC", "DG", "DT"]
    ATOMISTIC = [["P", "O5'", "C5'", "C4'", "C3'", "O3'"]] * 4

    def test_atomistic_dna_now_applicable(self):
        """Pre-wave-7 this returned False for every pdb_nucleic generator."""
        facade, fragment, inst = _mk_facade(_mk_universe(self.DNA_RES, self.ATOMISTIC))
        gen = PDBGeneratorNoSanitizeNucleic(SignaturesConfig())
        assert gen._is_applicable(inst, fragment, facade)
        genb = PDBBackboneGeneratorNoSanitizeNucleic(SignaturesConfig())
        assert genb._is_applicable(inst, fragment, facade)

    def test_coarse_grained_dna_still_applicable(self):
        """CG (single-atom residues) keeps its previous behavior."""
        facade, fragment, inst = _mk_facade(_mk_universe(self.DNA_RES, [["BB"]] * 4))
        gen = PDBGeneratorNoSanitizeNucleic(SignaturesConfig())
        assert gen._is_applicable(inst, fragment, facade)

    def test_protein_not_affected(self):
        facade, fragment, inst = _mk_facade(
            _mk_universe(["ALA"] * 4, [["N", "CA", "C", "O"]] * 4))
        gen = PDBGeneratorNoSanitizeNucleic(SignaturesConfig())
        assert not gen._is_applicable(inst, fragment, facade)

    def test_non_nucleic_rejected(self):
        facade, fragment, inst = _mk_facade(_mk_universe(["HEM"], [["FE", "NA", "NB"]]))
        gen = PDBGeneratorNoSanitizeNucleic(SignaturesConfig())
        assert not gen._is_applicable(inst, fragment, facade)
