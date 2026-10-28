"""W3 A3 (BH-038/BH-045/K-02): element-provenance guessing.

Production evidence (rootcause_elements.md): since 063fb8c63 "mass-first"
element guessing treats MDAnalysis' NAME-DERIVED guessed masses as if they
came from the topology. On element-less PDB/GRO that inverts every
ambiguity: IRE CAL -> Ca (should be C), HEM NA -> Na (should be N),
NBE -> Nb (should be N), PO4 bead -> Po, Martini beads -> Sc/Po/S. The
ion table was keyed on atom NAME, not RESNAME.

Fix contract pinned here (matches elem_scripts/sim.py):
1. masses are used only when NOT guessed by MDAnalysis
   (`masses_trusted`); PDB/GRO fall through to name rules.
2. single-atom NON-polymer residues: ion table by RESNAME, then atom
   name, then the existing logic (without mass when untrusted).
3. multi-atom residues: exact-name allowlist
   ^(CL|BR|FE|ZN|MG|MN|CU|NI|SE)digit*['*]?$ -> that element; else an
   organic first letter (C N O S P H F I); else old logic, no mass.
   Never from a name: CA CD CE NA NB NE HG OS SC PO CO.
4. coarse-grained systems are detected once per universe; elements stay
   blank with a warning (never Sc/Po/B).
"""

from __future__ import annotations

import numpy as np
import pytest
from MDAnalysis import Universe
from MDAnalysis.core.topology import Topology

from src_new.config.loader import RunConfig
from src_new.loader.repair import TopologyRepair


def _u(atoms_resname_groups, masses=None, masses_guessed=False):
    """atoms_resname_groups: list of (resname, [atom names]) — one residue
    per tuple. Returns (universe, repair)."""
    n_res = len(atoms_resname_groups)
    names, resnames, resids, segid_map = [], [], [], []
    atom_resindex = []
    for ri, (rn, atom_names) in enumerate(atoms_resname_groups):
        for nm in atom_names:
            names.append(nm)
            atom_resindex.append(ri)
            resids.append(None)
        resnames.append(rn)
    n = len(names)
    top = Topology(n, n_res, 1,
                   atom_resindex=atom_resindex,
                   residue_segindex=[0] * n_res, attrs=None)
    u = Universe(top)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
    u.add_TopologyAttr("segids", ["A"])
    if masses is not None:
        u.add_TopologyAttr("masses", masses)
        if masses_guessed:
            u._topology.masses._guessed = True
    u.load_new(np.zeros((1, n, 3), dtype=np.float32), format="memory")
    return u, TopologyRepair(u, RunConfig())


class TestMassProvenance:
    def test_distrusted_mass_does_not_invert_hem_na(self):
        """MDAnalysis guessed mass 22.99 for the pyrrole nitrogen NA of HEM
        (name-derived, the last letter dropped). Untrusted mass must not
        map NA -> Na; the multi-atom name rule gives nitrogen."""
        r = _u([("HEM", ["NA"])])[1]
        assert r._guess_single_element(
            "", "NA", 22.99, None, resname="HEM",
            residue_atom_count=43, mass_trusted=False) == "N"

    def test_distrusted_mass_ire_cal_is_carbon(self):
        """IRE (gefitinib) atom CAL: MDA guessed mass = CA 40.078, which
        the mass-first path currently turns into CALCIUM. Should be C."""
        r = _u([("IRE", ["CAL"])])[1]
        assert r._guess_single_element(
            "", "CAL", 40.078, None, resname="IRE",
            residue_atom_count=22, mass_trusted=False) == "C"

    def test_zero_mass_nbe_is_nitrogen(self):
        """NBE in a ligand: MDA drops the first letter (BE, not in the mass
        table, mass 0.0) and the 2-letter-first rule picks Nb. Should be N."""
        r = _u([("IRE", ["NBE"])])[1]
        assert r._guess_single_element(
            "", "NBE", 0.0, None, resname="IRE",
            residue_atom_count=22, mass_trusted=False) == "N"

    def test_trusted_mass_still_wins(self):
        """Real topology masses keep mass-first semantics (TPR/PSF/PRMTOP)."""
        r = _u([("LIG", ["CA"])])[1]
        assert r._guess_single_element(
            "", "CA", 40.078, None, resname="LIG",
            residue_atom_count=20, mass_trusted=True) == "Ca"

    def test_name_allowlist_cl_fe_mn_se(self):
        r = _u([("HEM", ["FE2", "CL1"])])[1]
        g = r._guess_single_element
        assert g("", "FE2", None, None, resname="LIG",
                 residue_atom_count=10, mass_trusted=False) == "Fe"
        assert g("", "CL1", None, None, resname="LIG",
                 residue_atom_count=10, mass_trusted=False) == "Cl"

    def test_never_from_two_letter_name(self):
        """CA CD CE NA NB NE HG OS SC PO CO must never become 2-letter
        elements from a name alone (B12 cobalt tolerable via trusted mass)."""
        r = _u([("LIG", ["C1"])])[1]
        g = r._guess_single_element
        cases = {"CA": "C", "CD": "C", "NA": "N", "NB": "N",
                 "NE": "N", "OS": "O", "SC": "S", "CO": "C", "PO": "P"}
        for nm, want in cases.items():
            got = g("", nm, None, None, resname="LIG",
                    residue_atom_count=20, mass_trusted=False)
            assert got == want, f"ligand {nm}: got {got}, want {want}"


class TestIonResnameLookup:
    def test_single_atom_ions_by_resname(self):
        """Ion table is keyed on RESNAME first, then atom name (the old
        code only used the atom name)."""
        r = _u([("MN", ["MN"]), ("CA", ["CA"]), ("CD", ["CD"])])[1]
        g = r._guess_single_element
        assert g("", "MN", None, None, resname="MN",
                 residue_atom_count=1, mass_trusted=False) == "Mn"
        assert g("", "CA", None, None, resname="CA",
                 residue_atom_count=1, mass_trusted=False) == "Ca"
        assert g("", "CD", None, None, resname="CD",
                 residue_atom_count=1, mass_trusted=False) == "Cd"


class TestCoarseGrainedDetection:
    def test_martini_bead_masses_detected(self):
        """trusted topology masses with < 50% matching an element -> CG."""
        u, r = _u([("GLY", ["BB", "SC1"]), ("ALA", ["BB", "SC1"]),
                   ("ION", ["NA"])], masses=[45.0, 72.0, 56.0, 54.0, 45.0])
        cg, _why = r._looks_coarse_grained(
            masses_trusted=not u._topology.masses.is_guessed)
        assert cg

    def test_bb_beads_shape_detected(self):
        """polymer residues averaging < 5 atoms with BB beads -> CG."""
        u, r = _u([("GLY", ["BB", "SC1"]), ("SER", ["BB", "SC1"]),
                   ("ARG", ["BB", "SC1", "SC2"])])
        cg, _why = r._looks_coarse_grained(masses_trusted=False)
        assert cg

    def test_real_protein_not_detected(self):
        u, r = _u([("ALA", ["CA", "CB", "C", "O", "N"]),
                   ("GLY", ["CA", "C", "O", "N", "H"])])
        cg, _why = r._looks_coarse_grained(masses_trusted=False)
        assert not cg


class TestFallbackIntegration:
    def test_element_less_universe_guesses_by_name_rules(self):
        """Full repair path on a HEM residue with name-derived masses:
        NA -> N, FE -> Fe, C1 -> C (masses are distrusted)."""
        u, r = _u([("HEM", ["NA", "FE2", "C1"])],
                  masses=[22.99, 55.845, 12.011], masses_guessed=True)
        r.guess_elements()
        elems = u.atoms.elements.tolist()
        assert elems == ["N", "Fe", "C"], elems
        # valid elements were recorded to the report
        assert r.report.elements_guessed >= 2

    def test_coarse_grained_left_blank_with_warning(self):
        u, r = _u([("GLY", ["BB", "SC1"]), ("ALA", ["BB", "SC1"])],
                  masses=[45.0, 72.0, 56.0, 54.0])
        r.guess_elements()
        assert all(e == "" for e in u.atoms.elements.tolist()), \
            u.atoms.elements.tolist()
        assert any("coarse" in w.lower()
                   for w in r.report.warnings), r.report.warnings
