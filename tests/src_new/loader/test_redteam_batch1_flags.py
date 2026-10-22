"""Red-team Batch 1 (loading/classification) regression tests.

Reproduces the auditor's probes for:
  A-01: protein/nucleic flags computed on the whole segment, not the
        representative fragment (protein + many ions => "small_molecule")
  A-03: HAS_ELEMENTS segment-wide: one blank element anywhere disables
        chemistry for a clean representative
  A-12: `fragment is selected` identity test never true => copy number 0
  A-02: fix_names groups by (resid, resname) across chains => chain B atoms
        renamed N->N1, CA->CA1
"""
from types import SimpleNamespace

import MDAnalysis as mda
import numpy as np

from src_new.loader.universe_facade import SegmentProperty
from src_new.loader.repair import TopologyRepair
from src_new.loader.universe_facade import LoadedUniverse, SegmentProperties, SegmentProperty


def _protein_with_ions(n_prot_res=200, n_ions=450):
    """One bonded ALA chain (5 atoms/res) + N mono-atomic NA ions, one segid."""
    atoms_per_prot_res = 5
    n_prot = n_prot_res * atoms_per_prot_res
    n = n_prot + n_ions
    resindex = []
    for ri in range(n_prot_res):
        resindex += [ri] * atoms_per_prot_res
    resindex += list(range(n_prot_res, n_prot_res + n_ions))
    u = mda.Universe.empty(n, n_residues=n_prot_res + n_ions, n_segments=1,
                           atom_resindex=resindex, trajectory=True)
    u.add_TopologyAttr("names", [f"AT{i}" for i in range(n)])
    u.add_TopologyAttr("resids", list(range(1, n_prot_res + n_ions + 1)))
    u.add_TopologyAttr("resnames",
                       ["ALA"] * n_prot_res + ["NA"] * n_ions)
    u.add_TopologyAttr("segids", ["SYST"])
    u.add_TopologyAttr("elements", ["C"] * n)
    u.add_bonds([(i, i + 1) for i in range(n_prot - 1)])
    return u


def _ligand_with_virtual_site():
    """9-atom bonded "ligand" + 4 atoms with one blank element, one segid."""
    n = 13
    resindex = [0] * 9 + [1] * 4
    u = mda.Universe.empty(n, n_residues=2, n_segments=1,
                           atom_resindex=resindex, trajectory=True)
    u.add_TopologyAttr("names", [f"A{i}" for i in range(n)])
    u.add_TopologyAttr("resids", [1, 2])
    u.add_TopologyAttr("resnames", ["LIG", "SOL"])
    u.add_TopologyAttr("segids", ["SYST"])
    u.add_TopologyAttr("elements", ["C", "C", "O", "H", "H", "H", "H", "H", "H",
                                    "O", "H", "H", ""])
    u.add_bonds([(i, i + 1) for i in range(8)] + [(9, 10), (10, 11)])
    return u


def _facade(u):
    facade = LoadedUniverse(
        universe=u,
        decision=SimpleNamespace(),
        repair_report=SimpleNamespace(),
        results=None,
    )
    return facade


class TestA01ProteinFlagScope:
    def test_protein_with_many_ions_stays_protein(self):
        n_ions = 450
        u = _protein_with_ions(n_ions=n_ions)
        facade = _facade(u)
        props = facade.get_segment_properties("SYST")
        assert props.flags[SegmentProperty.IS_PROTEIN.value] is True, (
            "protein representative must not be diluted by ions in the segment"
        )
        assert props.molecule_count == n_ions + 1


class TestA03ElementFlagScope:
    def test_blank_element_elsewhere_keeps_representative_chemistry(self):
        u = _ligand_with_virtual_site()
        facade = _facade(u)
        props = facade.get_segment_properties("SYST")
        assert props.flags[SegmentProperty.HAS_ELEMENTS.value] is True, (
            "representative fragment elements are complete; blank elements "
            "elsewhere in the segment must not disable chemistry"
        )


class TestA12CopyCountBondless:
    def test_bondless_segment_reports_one_molecule(self):
        u = mda.Universe.empty(4, n_residues=1, n_segments=1,
                               atom_resindex=[0, 0, 0, 0], trajectory=True)
        u.add_TopologyAttr("names", ["A0", "A1", "A2", "A3"])
        u.add_TopologyAttr("resids", [1])
        u.add_TopologyAttr("resnames", ["LIG"])
        u.add_TopologyAttr("segids", ["SYST"])
        u.add_TopologyAttr("elements", ["C", "C", "O", "H"])
        facade = LoadedUniverse(universe=u, decision=SimpleNamespace(),
                                repair_report=SimpleNamespace(), results=None)
        props = facade.get_segment_properties("SYST")
        assert props.molecule_count == 1


class TestA02FixNamesPerResindex:
    def test_second_chain_pairing_resid_resname_is_not_renamed(self):
        n = 4
        u = mda.Universe.empty(n, n_residues=2, n_segments=2,
                               atom_resindex=[0, 0, 1, 1],
                               residue_segindex=[0, 1], trajectory=True)
        u.add_TopologyAttr("names", ["N", "CA", "N", "CA"])
        u.add_TopologyAttr("resids", [1, 1])
        u.add_TopologyAttr("resnames", ["MET", "MET"])
        u.add_TopologyAttr("segids", ["A", "B"])
        report = SimpleNamespace(names_fixed=0)
        repair = TopologyRepair(u, report)
        repair.fix_names()
        assert report.names_fixed == 0, (
            "same (resid, resname) in another chain is a distinct residue; "
            "its atoms must not be renamed"
        )
        assert list(u.atoms.names) == ["N", "CA", "N", "CA"]
