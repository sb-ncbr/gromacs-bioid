"""c13 structure search (S1): every exported structure file carries PDB residue
names, never force-field names.

Live probe 2026-11-04 (T02 = MDBind 1N8U, AMBER): RCSB structure search answered
204 (no results) for the exported query file; the SAME file with only CYX->CYS
returned 1N8U as the top hit. _std_resname3 documented CYX->CYS but returned
every <=3-char name unchanged, and the Biopython writer (pdb_protein, the
pdb_struct query) only truncated names to 3 chars.
"""
from __future__ import annotations

import MDAnalysis as mda
import pytest

from src_new.identification.resolvers.mmcif import _mmcif_text_to_pdb
from src_new.signatures.generators import pdb as pdb_gen
from src_new.signatures.generators import topology_less_pdb as tl_gen

# (input residue name, expected PDB name)
_CASES = [
    ("CYX", "CYS"), ("CYM", "CYS"), ("CYS2", "CYS"),
    ("HIE", "HIS"), ("HID", "HIS"), ("HIP", "HIS"),
    ("HSD", "HIS"), ("HSE", "HIS"), ("HISE", "HIS"),
    ("ASH", "ASP"), ("GLH", "GLU"), ("LYN", "LYS"), ("LYSH", "LYS"),
    ("NHIE", "HIS"), ("CCYX", "CYS"),      # AMBER terminal forms
    ("NALA", "ALA"), ("CGLN", "GLN"),      # B-04 behaviour kept
    ("DA5", "DA"), ("DT3", "DT"), ("RU5", "U"), ("G3", "G"),
    ("ALA", "ALA"), ("cyx", "CYS"), (" HIE ", "HIS"),
    # genuine CCD components and ligands are left alone
    ("MSE", "MSE"), ("SEP", "SEP"), ("ACE", "ACE"), ("NME", "NME"),
    ("LIG", "LIG"), ("", ""),
]


@pytest.mark.parametrize("name,expected", _CASES)
def test_std_resname3_maps_force_field_names(name, expected):
    assert tl_gen._std_resname3(name) == expected


def test_single_normalizer_shared_by_all_writers():
    assert pdb_gen._std_resname3 is tl_gen._std_resname3


def _universe(resnames):
    """One residue per name: N, CA, C atoms (enough for every writer)."""
    names, resindex, positions = [], [], []
    for ri, _ in enumerate(resnames):
        for j, an in enumerate(("N", "CA", "C")):
            names.append(an)
            resindex.append(ri)
            positions.append((ri * 3.8 + j * 1.2, 0.0, 0.0))
    u = mda.Universe.empty(len(names), n_residues=len(resnames), n_segments=1,
                           atom_resindex=resindex, trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("elements", [n[0] for n in names])
    u.add_TopologyAttr("resids", list(range(1, len(resnames) + 1)))
    u.add_TopologyAttr("resnums", list(range(1, len(resnames) + 1)))
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("chainIDs", ["A"] * len(names))
    u.add_TopologyAttr("segids", ["S"])
    u.atoms.positions = positions
    return u


_FF = ["NALA", "CYX", "HIE", "ASH", "CCYX"]
_PDB = ["ALA", "CYS", "HIS", "ASP", "CYS"]


def _resnames_in(pdb_text):
    out = []
    for ln in pdb_text.splitlines():
        if ln.startswith(("ATOM", "HETATM")):
            name = ln[17:20].strip()
            if not out or out[-1][0] != ln[22:26]:
                out.append((ln[22:26], name))
    return [n for _, n in out]


@pytest.mark.parametrize("only_backbone", [False, True])
def test_biopython_writer_emits_pdb_names(only_backbone):
    """pdb_protein / pdb_backbone_protein (the pdb_struct RCSB query)."""
    u = _universe(_FF)
    text = pdb_gen.fragment_to_pdb_biopython(
        u.atoms, only_backbone,
        backbone_selector=pdb_gen._protein_backbone_atom if only_backbone else None)
    assert _resnames_in(text) == _PDB


def test_direct_writer_emits_pdb_names():
    text = pdb_gen.fragment_to_pdb_direct(_universe(_FF).atoms, False,
                                          include_bonds=False)
    assert _resnames_in(text) == _PDB


def test_ca_only_writer_emits_pdb_names():
    """ca_only_pdb (Foldseek / AlphaFind / structure verification)."""
    text = tl_gen.fragment_to_pdb_ca_only(_universe(_FF).atoms)
    assert _resnames_in(text) == _PDB


def test_mmcif_route_conversion_emits_pdb_names():
    """mmcif_struct converts our minimal mmCIF to PDB for RCSB."""
    rows = []
    for i, rn in enumerate(_FF, start=1):
        rows.append(f"ATOM {i} C CA . {rn} A 1 {i} ? {i * 3.8:.3f} 0.000 0.000 1.00 0.00")
    text = "\n".join([
        "data_mock", "loop_",
        "_atom_site.group_PDB", "_atom_site.id", "_atom_site.type_symbol",
        "_atom_site.label_atom_id", "_atom_site.label_alt_id",
        "_atom_site.label_comp_id", "_atom_site.label_asym_id",
        "_atom_site.label_entity_id", "_atom_site.label_seq_id",
        "_atom_site.pdbx_PDB_ins_code", "_atom_site.Cartn_x",
        "_atom_site.Cartn_y", "_atom_site.Cartn_z", "_atom_site.occupancy",
        "_atom_site.B_iso_or_equiv",
        *rows, "#", ""])
    pdb_text = _mmcif_text_to_pdb(text)
    assert pdb_text is not None
    assert _resnames_in(pdb_text) == _PDB
