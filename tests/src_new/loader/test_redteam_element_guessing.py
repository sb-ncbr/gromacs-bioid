"""Wave-2 item 5 (GitHub #2): element guessing order + ion residue names.

The old `_guess_single_element` checked the 1-letter name prefix FIRST and
its 2-letter lookup compared `.upper()` against title-case table keys — so it
could never match — and mass came LAST. Consequences, reproduced on repo
fixtures: CHARMM `system.psf` gave SOD → S and CLA → C; `PE_CL_530Run.gro`
gave every SOD → S; NA → N and CL → C even with mass 35.45 present.

New priority: water/virtual-site guards → MASS (when > 0.5) → single-atom
ion residue names → residue-context-aware name prefixes (2-letter properly
capitalised first for single-atom/non-polymer residues; 1-letter first inside
protein/NA residues so protein CA stays carbon) → atom type → mass fallback.
"""

from pathlib import Path

import numpy as np
import pytest
from MDAnalysis import Universe
from MDAnalysis.core.topology import Topology
from MDAnalysis.core.topologyattrs import (
    Atomtypes,
    Elements,
    Masses,
    Resids,
    Resnames,
    Segids,
)

from src_new.config.loader import RunConfig
from src_new.loader.repair import TopologyRepair

DATA = Path(__file__).resolve().parents[2] / "data"
PSF = DATA / "charmm_psf_pdb" / "system.psf"
GRO = DATA / "gromacs_tpr_gro" / "PE_CL_530Run.gro"


def _universe(atoms, resname="LIG", masses=None, types=None):
    """atoms: list of (index, name), all in ONE residue (resname)."""
    n = len(atoms)
    top = Topology(n, 1, 1, attrs=None)
    u = Universe(top)
    u.add_TopologyAttr("names", [a[1] for a in atoms])
    u.add_TopologyAttr("resnames", [resname])
    u.add_TopologyAttr("resids", [1])
    u.add_TopologyAttr("segids", ["SYSTEM"])
    if types is not None:
        u.add_TopologyAttr("types", types)
    if masses is not None:
        u.add_TopologyAttr("masses", masses)
    u.load_new(np.zeros((1, n, 3), dtype=np.float32), format="memory")
    return u


def _repair(u):
    return TopologyRepair(u, RunConfig())


class TestGuessSingleElementOrder:
    def test_mass_beats_name(self):
        r = _repair(_universe([(0, "CL")], resname="SYS", masses=[35.45]))
        # 35.45 is chlorine, not carbon — mass wins over the 1-letter prefix
        assert r._guess_single_element("", "CL", 35.45, None, resname="SYS", residue_atom_count=1) == "Cl"

    def test_mass_unambiguous_na_ca(self):
        r = _repair(_universe([(0, "NA")]))
        assert r._guess_single_element("", "NA", 22.99, None, resname="SYS", residue_atom_count=1) == "Na"
        assert r._guess_single_element("", "CA", 40.078, None, resname="SYS", residue_atom_count=1) == "Ca"

    def test_single_atom_ion_residue_names(self):
        r = _repair(_universe([(0, "SOD")]))
        g = r._guess_single_element
        assert g("", "SOD", None, None, resname="SOD", residue_atom_count=1) == "Na"
        assert g("", "CLA", None, None, resname="CLA", residue_atom_count=1) == "Cl"
        assert g("", "POT", None, None, resname="POT", residue_atom_count=1) == "K"
        assert g("", "CL-", None, None, resname="CL-", residue_atom_count=1) == "Cl"
        assert g("", "NA+", None, None, resname="NA+", residue_atom_count=1) == "Na"
        assert g("", "ZN2", None, None, resname="ZN2", residue_atom_count=1) == "Zn"

    def test_protein_ca_stays_carbon(self):
        r = _repair(_universe([(0, "CA"), (1, "N"), (2, "C")], resname="ALA"))
        # inside a protein residue the 1-letter prefix comes first: CA -> C
        assert r._guess_single_element("", "CA", None, None, resname="ALA", residue_atom_count=3) == "C"

    def test_ligand_two_letter_before_one(self):
        r = _repair(_universe([(0, "CL1"), (1, "BR1"), (2, "C1")], resname="LIG"))
        g = r._guess_single_element
        assert g("", "CL1", None, None, resname="LIG", residue_atom_count=30) == "Cl"
        assert g("", "BR1", None, None, resname="LIG", residue_atom_count=30) == "Br"

    def test_ligand_ca_maps_to_carbon(self):
        # W3 A3 (BH-038): contract corrected 2026-10-28. The wave-2 rule
        # turned a LIGAND's `CA` atom into calcium — wrong on element-less
        # PDB/GRO: on ligands, CA/CD/CE/NA/NB/... are organic names, never
        # two-letter elements (the proposed-fix "never from a name" list).
        # Trusted topology masses still resolve real calcium (mass-first).
        r = _repair(_universe([(0, "CA")], resname="LIG"))
        assert r._guess_single_element("", "CA", None, None, resname="LIG", residue_atom_count=20) == "C"

    def test_water_and_virtual_site_guards_unchanged(self):
        r = _repair(_universe([(0, "OW"), (1, "HW1"), (2, "MW")]))
        g = r._guess_single_element
        assert g("", "OW", None, None) == "O"
        assert g("", "HW1", None, None) == "H"
        assert g("", "MW", None, None) == ""


class TestFixtureRegressions:
    def test_charmm_psf_ions(self):
        u = Universe(str(PSF))
        repair = TopologyRepair(u, RunConfig())
        repair.guess_elements()
        sod = u.select_atoms("resname SOD")
        cla = u.select_atoms("resname CLA")
        assert len(sod) >= 1 and set(sod.elements) == {"Na"}
        assert len(cla) >= 1 and set(cla.elements) == {"Cl"}

    def test_gro_sodium_ions(self):
        u = Universe(str(GRO))
        repair = TopologyRepair(u, RunConfig())
        repair.guess_elements()
        sod = u.select_atoms("resname SOD")
        assert len(sod) > 100
        assert set(sod.elements) == {"Na"}
