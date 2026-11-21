"""2026-11-21 mdval audit items 4 (lipids) and 8b (coarse-grained).

Item 4: the balanced preset identified PAPC/PAPS/DSPC/PSM... never — the
lipid shorthand map had 35 CHARMM names; Drude lipids (zenodo/7602770 POPE
182 atoms) failed every RDKit generator on element-less Drude particles;
strained frames (figshare/8202149) bonded geminal hydrogens to each other.
Item 8b: a coarse-grained run (zenodo/10018409, 3956797) typed Martini
water "W" as tungsten ion, and every molecule read "not identified".
"""
from __future__ import annotations

import json
import re
import types
from pathlib import Path

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")

from MDAnalysis.core.topology import Topology  # noqa: E402

from src_new.config.loader import RunConfig, SignaturesConfig  # noqa: E402
from src_new.input.models import LoadDecision  # noqa: E402
from src_new.loader.fragment_store import FragmentStore  # noqa: E402
from src_new.loader.repair import TopologyRepair, RepairReport, guess_bonds_union  # noqa: E402
from src_new.loader.universe_facade import LoadedUniverse  # noqa: E402
from src_new.molecules.instances import (  # noqa: E402
    LIPID_RESNAMES, MoleculeInstance, MoleculeType)
from src_new.molecules.lipid_names import ALL_ATOM_SHORTHAND, MARTINI_SHORTHAND  # noqa: E402
from src_new.signatures.forcefield_maps import LIPID_FORCEFIELD_MAPS  # noqa: E402

NAME_TABLES = Path(__file__).resolve().parents[3] / "src_new" / "identification" / "name_tables"


def _universe(groups, masses=None, elements=None, positions=None, segment_per_residue=False):
    """groups: [(resname, [atom names])], one residue each; one segment, or
    one per residue (a bond-less CG fixture: segments stand in for bonds)."""
    names, resnames, atom_resindex = [], [], []
    for ri, (rn, atom_names) in enumerate(groups):
        names += atom_names
        atom_resindex += [ri] * len(atom_names)
        resnames.append(rn)
    n, n_res = len(names), len(groups)
    n_seg = n_res if segment_per_residue else 1
    segindex = list(range(n_res)) if segment_per_residue else [0] * n_res
    u = mda.Universe(Topology(n, n_res, n_seg, atom_resindex=atom_resindex,
                              residue_segindex=segindex, attrs=None))
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("resids", list(range(1, n_res + 1)))
    u.add_TopologyAttr("segids", [f"S{i}" for i in range(n_seg)] if segment_per_residue else ["MEMB"])
    if masses is not None:
        u.add_TopologyAttr("masses", masses)
    if elements is not None:
        u.add_TopologyAttr("elements", elements)
    pos = np.zeros((1, n, 3), dtype=np.float32) if positions is None else \
        np.asarray([positions], dtype=np.float32)
    u.load_new(pos, format="memory")
    return u


MARTINI_POPE = ["NH3", "PO4", "GL1", "GL2", "C1A", "D2A", "C3A", "C4A",
                "C1B", "C2B", "C3B", "C4B"]


def _martini_membrane(n_lipids=6, n_water=10):
    groups = [("POPE", list(MARTINI_POPE)) for _ in range(n_lipids)]
    groups += [("W", ["W"]) for _ in range(n_water)]
    groups += [("WF", ["WF"]), ("ION", ["NA+"]), ("ION", ["CL-"])]
    return _universe(groups, segment_per_residue=True)


# --------------------------------------------------------------------------
# item 4 — the shorthand table


def _formula_carbons(shorthand):
    """carbons of a glycerophospholipid / SM / Cer shorthand."""
    cls = shorthand.split("(", 1)[0]
    acyl = sum(int(c) for c in re.findall(r"(?:^|[(/])d?(\d+):\d+", shorthand))
    base = {"PC": 8, "PE": 5, "PS": 6, "PG": 6, "PA": 3, "PI": 9, "PIP": 9,
            "PIP2": 9, "CL": 9, "SM": 5, "Cer": 0}[cls]
    return base + acyl


def test_charmm_shorthands_match_the_maps_provenance_carbons():
    """every CHARMM36 key of maps_provenance.json with a shorthand has the
    carbon count of the topology's own structure"""
    prov = {r["name"]: r for r in json.loads(
        (NAME_TABLES / "maps_provenance.json").read_text())}
    checked = 0
    for name, shorthand in ALL_ATOM_SHORTHAND.items():
        if name not in prov or "(" not in shorthand:
            continue
        carbons = int(re.search(r"C(\d+)", prov[name]["formula"]).group(1))
        assert _formula_carbons(shorthand) == carbons, (name, shorthand, prov[name]["formula"])
        checked += 1
    assert checked >= 140


def test_audit_names_have_their_lipid_maps_shorthand():
    sh = LIPID_FORCEFIELD_MAPS["charmm36"]
    assert sh["PAPC"] == "PC(16:0/20:4(5Z,8Z,11Z,14Z))"
    assert sh["PAPS"] == "PS(16:0/20:4(5Z,8Z,11Z,14Z))"
    assert sh["DPSM"] == sh["PSM"] == "SM(d18:1/16:0)"
    assert sh["DSPC"] == "PC(18:0/18:0)"
    assert sh["SOPE"] == "PE(18:0/18:1(9Z))"
    assert sh["SDPC"] == "PC(18:0/22:6(4Z,7Z,10Z,13Z,16Z,19Z))"
    assert sh["DLIPC"] == sh["DLIPC".upper()] == "PC(18:2(9Z,12Z)/18:2(9Z,12Z))"
    assert sh["POPE"] == "PE(16:0/18:1(9Z))" and sh["DPPC"] == "PC(16:0/16:0)"
    assert sh["NSM"] == "SM(d18:1/24:1(15Z))"
    assert sh["POPI24"] == "PIP2(16:0/18:1(9Z))"
    # Martini names: the documented all-atom parent (shown by name only)
    assert MARTINI_SHORTHAND["PIPC"] == "PC(16:0/18:2(9Z,12Z))"
    assert MARTINI_SHORTHAND["POP2"] == "PIP2(16:0/18:1(9Z))"
    assert LIPID_FORCEFIELD_MAPS["martini"]["POPE"] == "PE(16:0/18:1(9Z))"


def test_every_shorthand_queries_a_lipid_maps_species():
    from src_new.identification.resolvers.lipid import species_shorthand
    for name, shorthand in ALL_ATOM_SHORTHAND.items():
        if shorthand in ("CL", "PI"):
            continue
        assert species_shorthand(shorthand), (name, shorthand)
    assert species_shorthand(ALL_ATOM_SHORTHAND["PAPS"]) == "PS 36:4"
    assert species_shorthand(ALL_ATOM_SHORTHAND["PSM"]) == "SM 34:1;O2"


def test_maps_json_lipid_keys_are_typed_lipid():
    prov = json.loads((NAME_TABLES / "maps_provenance.json").read_text())
    lipid_like = re.compile(r"(?i)phosphati|glycero|sphingomyelin|ceramide|cardiolipin|"
                            r"cholesterol|sterol|pyrophos|lyso")
    keys = {r["name"] for r in prov if lipid_like.search(r["molecule"])
            and not r["name"].startswith(("CHS", "FOS", "CYFOS", "FOIS", "UFOS"))}
    missing = sorted(k for k in keys if k.upper() not in LIPID_RESNAMES)
    assert not missing, missing


def _props(atoms):
    return types.SimpleNamespace(flags={}, atom_count_fragment=atoms)


def _frag(resnames, elements, names=None):
    names = names or ["X"] * len(elements)
    return types.SimpleNamespace(residues=types.SimpleNamespace(resnames=resnames),
                                 atoms=types.SimpleNamespace(elements=elements, names=names))


def test_lipid_names_need_lipid_atoms():
    cls = LoadedUniverse._classify_molecule_type
    dspc = ["C"] * 44 + ["O"] * 8 + ["P", "N"]
    assert cls(_props(54), _frag(["DSPC"], dspc)) == MoleculeType.LIPID
    # a C2H5 piece of a PBC-broken POPC is not "the lipid"
    assert cls(_props(7), _frag(["POPC"], ["C", "C", "H", "H", "H", "H", "H"])) != MoleculeType.LIPID
    # CCD "PI" is the phosphate ion
    assert cls(_props(5), _frag(["PI"], ["P", "O", "O", "O", "O"])) != MoleculeType.LIPID


def test_lipid21_split_is_typed_lipid_by_name():
    cls = LoadedUniverse._classify_molecule_type
    atoms = ["C"] * 42 + ["O"] * 8 + ["P", "N"]
    assert cls(_props(52), _frag(["PC", "PA", "OL"], atoms)) == MoleculeType.LIPID


# --------------------------------------------------------------------------
# item 4 — Drude particles and guessed H-H bonds


def _drude_ethanol():
    """C-C-O + H + Drude particles (mass 0.4, no element) bonded to heavy atoms."""
    names = ["C1", "C2", "O1", "H11", "H12", "H13", "H21", "H22", "HO", "DC1", "DC2", "DO1"]
    elements = ["C", "C", "O", "H", "H", "H", "H", "H", "H", "", "", ""]
    masses = [11.6, 11.6, 15.6, 1.008, 1.008, 1.008, 1.008, 1.008, 1.008, 0.4, 0.4, 0.4]
    u = _universe([("ETOH", names)], masses=masses, elements=elements)
    u.add_TopologyAttr("charges", [-0.1, 0.2, -0.2, 0.09, 0.09, 0.09, 0.09, 0.09, 0.4,
                                   -1.0, -1.0, -1.5])
    u.add_TopologyAttr("bonds", [(0, 1), (1, 2), (0, 3), (0, 4), (0, 5), (1, 6), (1, 7),
                                 (2, 8), (0, 9), (1, 10), (2, 11)])
    return u


def test_drude_particles_are_stripped_from_rdkit_generators():
    from src_new.signatures.generators._perceive_cache import (
        _external_cut_counts, _net_charge, real_atoms)
    u = _drude_ethanol()
    frag = real_atoms(u.atoms)
    assert frag.n_atoms == 9 and set(frag.elements) == {"C", "O", "H"}
    assert _external_cut_counts(frag) == {}          # no H caps for Drude bonds
    assert _net_charge(frag) == round(sum(u.atoms.charges))  # Drude charge kept
    assert real_atoms(frag) is frag                  # nothing left to strip


def test_drude_lipid_gets_a_smiles():
    from src_new.signatures.generators.smiles import SimpleSmilesGenerator
    from src_new.signatures.generators._perceive_cache import clear_cache
    clear_cache()
    u = _drude_ethanol()
    facade = types.SimpleNamespace(get_segment_properties=lambda seg: types.SimpleNamespace(
        flags={"has_elements": True}))
    inst = MoleculeInstance(instance_id="mol_MEMB", molecule_type=MoleculeType.SMALL_MOLECULE)
    gen = SimpleSmilesGenerator(SignaturesConfig())
    assert gen.is_applicable(inst, u.atoms, facade)
    assert gen.generate(inst, u.atoms, facade) == "CCO"


def test_guessed_geminal_h_h_bond_is_dropped():
    # CH2 with its two hydrogens 0.8 A apart (strained frame): C-H, C-H, H-H
    pos = [[0, 0, 0], [1.0, 0.4, 0], [1.0, -0.4, 0], [-1.5, 0, 0]]
    u = _universe([("LIG", ["C1", "H1", "H2", "C2"])], elements=["C", "H", "H", "C"],
                  masses=[12.011, 1.008, 1.008, 12.011], positions=pos)
    u.add_TopologyAttr("types", ["C", "H", "H", "C"])
    guess_bonds_union(u, vdwradii={"C": 1.7, "H": 1.1}, fudge_factor=0.55)
    pairs = {tuple(sorted(map(int, b))) for b in u.atoms.bonds.indices}
    assert (1, 2) not in pairs and {(0, 1), (0, 2), (0, 3)} <= pairs


def test_h2_keeps_its_bond():
    u = _universe([("H2", ["H1", "H2"])], elements=["H", "H"], masses=[1.008, 1.008],
                  positions=[[0, 0, 0], [0.74, 0, 0]])
    u.add_TopologyAttr("types", ["H", "H"])
    guess_bonds_union(u, vdwradii={"H": 1.1}, fudge_factor=0.55)
    assert len(u.atoms.bonds) == 1


# --------------------------------------------------------------------------
# item 8b — coarse-grained verdict, typing and by-name lead


def test_martini_membrane_in_polarizable_water_is_detected():
    # zenodo/10612097: lipids + PW water (W/WP/WM); masses not trusted
    groups = [("POPC", ["NC3", "PO4", "GL1", "GL2", "C1A", "D2A", "C3A", "C4A",
                        "C1B", "C2B", "C3B", "C4B"]) for _ in range(6)]
    groups += [("PW", ["W", "WP", "WM"]) for _ in range(2)]
    u = _universe(groups)
    cg, why = TopologyRepair(u, RunConfig())._looks_coarse_grained(masses_trusted=False)
    assert cg, why


def test_small_lipids_alone_are_coarse_grained():
    # bead names outside the vocabulary, but 12-bead lipids
    groups = [("DPPC", [f"B{i}" for i in range(12)]) for _ in range(8)]
    cg, why = TopologyRepair(_universe(groups), RunConfig())._looks_coarse_grained(masses_trusted=False)
    assert cg and "lipid residues median 12" in why


def test_atomistic_membrane_is_not_coarse_grained():
    names = [f"C{i}" for i in range(40)] + [f"H{i}" for i in range(80)] + ["N", "P"] + [f"O{i}" for i in range(8)]
    groups = [("DPPC", names) for _ in range(6)]
    cg, _ = TopologyRepair(_universe(groups), RunConfig())._looks_coarse_grained(masses_trusted=False)
    assert not cg


def _cg_store():
    u = _martini_membrane()
    rep = TopologyRepair(u, RunConfig()).run()
    facade = LoadedUniverse(universe=u, decision=LoadDecision(input_kind=None, selected_strategy="t"),
                            repair_report=rep)
    return rep, facade, FragmentStore(facade)


def test_repair_report_carries_the_coarse_grained_verdict():
    rep, _facade, _store = _cg_store()
    d = rep.to_dict()
    assert d["coarse_grained"] is True and d["coarse_grained_model"] == "Martini"
    assert d["elements_source"] == "coarse_grained_blank" and d["coarse_grained_reason"]
    assert RepairReport().to_dict()["coarse_grained"] is False


def test_cg_water_is_water_not_tungsten_and_molecules_carry_the_verdict():
    _rep, _facade, store = _cg_store()
    by_res = {}
    for inst in store.get_all_instances():
        by_res.setdefault(inst.resnames[0], []).append(inst)
    assert {i.molecule_type for i in by_res["W"]} == {MoleculeType.WATER}
    assert {i.molecule_type for i in by_res["WF"]} == {MoleculeType.WATER}
    assert {i.molecule_type for i in by_res["ION"]} == {MoleculeType.ION}
    pope = by_res["POPE"][0]
    assert pope.molecule_type == MoleculeType.LIPID
    assert pope.provenance["coarse_grained"] == {
        "model": "Martini", "residue": "POPE", "by_name": "PE(16:0/18:1(9Z))"}
    assert by_res["W"][0].provenance["coarse_grained"] == {"model": "Martini", "residue": "W"}


def test_single_bead_never_gets_an_element_from_its_name():
    cls = LoadedUniverse._classify_molecule_type
    w = _frag(["SOL"], [""], names=["W"])  # elements blank (CG) — name W
    assert cls(_props(1), w) == MoleculeType.ION          # atomistic fallback: tungsten
    assert cls(_props(1), w, coarse_grained=True) == MoleculeType.WATER
    odd = _frag(["XX"], [""], names=["FE"])
    assert cls(_props(1), odd, coarse_grained=True) == MoleculeType.UNKNOWN


def test_fragment_segments_record_coarse_grained():
    from src_new.results.results_manager import ResultsManager
    u = _martini_membrane()
    rep = TopologyRepair(u, RunConfig()).run()
    results = ResultsManager.__new__(ResultsManager)
    stored = {}
    results.set_data = lambda key, value: stored.__setitem__(key, value)
    facade = LoadedUniverse(universe=u, decision=LoadDecision(input_kind=None, selected_strategy="t"),
                            repair_report=rep)
    FragmentStore(facade, results)
    entries = stored["fragments/segments"]
    pope = [e for e in entries if e["type"] == "lipid"]
    assert pope and pope[0]["coarse_grained"]["by_name"] == "PE(16:0/18:1(9Z))"
    assert all("coarse_grained" in e for e in entries)


def test_lipid_shorthand_skips_coarse_grained_molecules():
    from src_new.signatures.generators.lipid import LipidShorthandGenerator
    gen = LipidShorthandGenerator(SignaturesConfig())
    cg = MoleculeInstance(instance_id="m", molecule_type=MoleculeType.LIPID,
                          provenance={"coarse_grained": {"model": "Martini", "residue": "POPE"}})
    aa = MoleculeInstance(instance_id="m", molecule_type=MoleculeType.LIPID)
    assert not gen.is_applicable(cg, None, None)
    assert gen.is_applicable(aa, None, None)
