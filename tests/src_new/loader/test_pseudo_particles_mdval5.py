"""mdval audit item 5 (2026-11-21): CHARMM Drude inputs (zenodo 7596011,
7916287, 7932361) broke every chemical signature with "Element '' not
found": each POPC carried 60 Drude (D*) and lone-pair (LP*) particles and
SWM4 water OM + DOH2, all handed to RDKit as atoms. Pseudo particles
(Drude, lone pairs, virtual sites) must stay out of the chemistry: element
and mass guessing, bond guessing, fragments, compositions, signatures.
Also: the PSF+PDB name check must accept the PDB's 4-character truncation
(PSF 'DC210' vs PDB 'DC21')."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

pytest.importorskip("MDAnalysis")
from MDAnalysis import Universe

from src_new.config.loader import RunConfig, SignaturesConfig
from src_new.loader.repair import (
    TopologyRepair, find_pseudo_particles)
from src_new.loader.universe_facade import LoadedUniverse

METHANOL_KEY = "OKKJLVBELUTLKV-UHFFFAOYSA-N"
WATER_KEY = "XLYOFNOQVPJJNP-UHFFFAOYSA-N"

# Drude methanol (a lipid-like stand-in: Drude on every heavy atom, two lone
# pairs on the oxygen), SWM4 water (OM + DOH2) and Drude ions (SOD/DSOD,
# CLA/DCLA in two-atom residues), CHARMM Drude style names/types/masses.
_MEOH = [  # name, type, mass, xyz (relative)
    ("CB", "CD33A", 11.611, (0.000, 0.000, 0.000)),
    ("OG", "OD31A", 15.599, (1.430, 0.000, 0.000)),
    ("HG1", "HDP1A", 1.008, (1.750, 0.900, 0.000)),
    ("HB1", "HDA3A", 1.008, (-0.360, 1.030, 0.000)),
    ("HB2", "HDA3A", 1.008, (-0.360, -0.510, 0.890)),
    ("HB3", "HDA3A", 1.008, (-0.360, -0.510, -0.890)),
    ("DCB", "DRUD", 0.400, (0.050, 0.020, 0.000)),
    ("DOG", "DRUD", 0.400, (1.470, 0.030, 0.010)),
    ("LPGA", "LPD", 0.000, (1.600, -0.200, 0.250)),
    ("LPGB", "LPD", 0.000, (1.600, -0.200, -0.250)),
]
_MEOH_BONDS = [(0, 1), (1, 2), (0, 3), (0, 4), (0, 5),
               (0, 6), (1, 7), (1, 8), (1, 9)]  # PSF: Drude/LP bonded to parent
_SWM4 = [
    ("OH2", "ODW", 15.59943, (0.000, 0.000, 0.000)),
    ("H1", "HDW", 1.008, (0.9572, 0.000, 0.000)),
    ("H2", "HDW", 1.008, (-0.240, 0.927, 0.000)),
    ("OM", "LPDW", 0.000, (0.150, 0.150, 0.000)),
    ("DOH2", "DRUD", 0.400, (0.030, -0.020, 0.010)),
]
_SWM4_BONDS = [(0, 1), (0, 2), (1, 2), (0, 3), (0, 4)]
_SOD = [("SOD", "SODD", 22.590, (0.0, 0.0, 0.0)),
        ("DSOD", "DRUD", 0.400, (0.05, 0.0, 0.0))]
_CLA = [("CLA", "CLAD", 35.053, (0.0, 0.0, 0.0)),
        ("DCLA", "DRUD", 0.400, (0.0, 0.08, 0.0))]


def _drude_system(with_masses=True, with_types=True, with_bonds=True,
                  n_meoh=2, n_water=2):
    """[(segid, resname, atoms, bonds, offset_xyz)] -> CHARMM-Drude-like
    universe without elements (a PSF carries none)."""
    residues = []
    for k in range(n_meoh):
        residues.append(("MEMB", "MEOH", _MEOH, _MEOH_BONDS, (8.0 * k, 0, 0)))
    for k in range(n_water):
        residues.append(("TIP3", "SWM4", _SWM4, _SWM4_BONDS, (8.0 * k, 8.0, 0)))
    residues.append(("IONS", "SOD", _SOD, [(0, 1)], (0, 16.0, 0)))
    residues.append(("IONS", "CLA", _CLA, [(0, 1)], (8.0, 16.0, 0)))
    segids = []
    for seg, *_ in residues:
        if seg not in segids:
            segids.append(seg)
    atom_resindex, names, types, masses, pos, bonds = [], [], [], [], [], []
    for ri, (_seg, _rn, atoms, rbonds, off) in enumerate(residues):
        base = len(names)
        for nm, ty, m, xyz in atoms:
            atom_resindex.append(ri)
            names.append(nm)
            types.append(ty)
            masses.append(m)
            pos.append(np.add(xyz, off))
        bonds += [(base + a, base + b) for a, b in rbonds]
    u = Universe.empty(len(names), n_residues=len(residues),
                       n_segments=len(segids), atom_resindex=atom_resindex,
                       residue_segindex=[segids.index(r[0]) for r in residues],
                       trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resnames", [r[1] for r in residues])
    u.add_TopologyAttr("resids", list(range(1, len(residues) + 1)))
    u.add_TopologyAttr("segids", segids)
    if with_types:
        u.add_TopologyAttr("types", types)
    if with_masses:
        u.add_TopologyAttr("masses", masses)
    if with_bonds:
        u.add_TopologyAttr("bonds", bonds)
    u.load_new(np.array(pos, dtype=np.float32)[np.newaxis], format="memory")
    return u


def _pseudo_names(u, idx):
    return sorted({str(u.atoms[i].name) for i in idx})


PSEUDO_NAMES = sorted({"DCB", "DOG", "LPGA", "LPGB", "OM", "DOH2", "DSOD", "DCLA"})


class TestDetection:
    def test_trusted_masses(self):
        u = _drude_system()
        idx = find_pseudo_particles(u)
        assert _pseudo_names(u, idx) == PSEUDO_NAMES
        assert len(idx) == 2 * 4 + 2 * 2 + 2

    def test_names_and_proximity_without_masses(self):
        """PDB-only fallback: no masses, no types — names (LP*, OM in water)
        and D<parent> within 0.5 A decide."""
        u = _drude_system(with_masses=False, with_types=False, with_bonds=False)
        assert _pseudo_names(u, find_pseudo_particles(u)) == PSEUDO_NAMES

    def test_drude_type_without_masses(self):
        u = _drude_system(with_masses=False, with_bonds=False)
        u.atoms.positions = u.atoms.positions * 0 + np.arange(len(u.atoms))[:, None] * 3.0
        found = _pseudo_names(u, find_pseudo_particles(u))
        # far from their parents now: only type DRUD / LP / OM names remain
        assert found == PSEUDO_NAMES

    def test_pdb_truncated_drude_name(self):
        """PDB cuts 'DC210' to 'DC21'; it sits on C210, not on C21."""
        u = Universe.empty(3, n_residues=1, n_segments=1, atom_resindex=[0, 0, 0],
                           trajectory=True)
        u.add_TopologyAttr("names", ["C21", "C210", "DC21"])
        u.add_TopologyAttr("resnames", ["POPC"])
        u.add_TopologyAttr("segids", ["MEMB"])
        u.load_new(np.array([[[0, 0, 0], [5.0, 0, 0], [5.1, 0, 0]]],
                            dtype=np.float32), format="memory")
        assert _pseudo_names(u, find_pseudo_particles(u)) == ["DC21"]

    def test_real_atoms_are_not_pseudo(self):
        """A deuterium 1 A from its N, a ligand oxygen named OM, and an atom
        named LP1 with a real topology mass stay atoms."""
        u = Universe.empty(4, n_residues=2, n_segments=1,
                           atom_resindex=[0, 0, 1, 1], trajectory=True)
        u.add_TopologyAttr("names", ["N", "DN", "C1", "OM"])
        u.add_TopologyAttr("resnames", ["LIG", "MET"])
        u.add_TopologyAttr("segids", ["L"])
        u.load_new(np.array([[[0, 0, 0], [1.0, 0, 0], [5, 0, 0], [6.4, 0, 0]]],
                            dtype=np.float32), format="memory")
        assert find_pseudo_particles(u) == []
        u.add_TopologyAttr("masses", [14.0, 2.0, 12.0, 16.0])
        u.atoms.names = ["N", "DN", "LP1", "OM"]
        assert find_pseudo_particles(u) == []

    def test_mostly_massless_topology_is_not_all_pseudo(self):
        """A topology whose masses are mostly 0 carries no mass information:
        the name rules decide instead of stripping every atom."""
        u = _drude_system()
        u.atoms.masses = np.zeros(len(u.atoms))
        assert _pseudo_names(u, find_pseudo_particles(u)) == PSEUDO_NAMES


class TestElementGuessing:
    def _repair(self, **kw):
        u = _drude_system(**kw)
        report = TopologyRepair(u, RunConfig()).run()
        return u, report

    def test_psf_like_elements_masses_bonds(self):
        u, report = self._repair()
        by_name = {}
        for a in u.atoms:
            by_name.setdefault(str(a.name), set()).add(
                (str(a.element), round(float(a.mass), 3)))
        for nm in PSEUDO_NAMES:
            assert {e for e, _m in by_name[nm]} == {""}, nm
        assert by_name["OM"] == {("", 0.0)}, "OM's trusted 0 mass overwritten"
        assert by_name["SOD"] == {("Na", 22.59)}
        assert by_name["CLA"] == {("Cl", 35.053)}
        assert by_name["CB"] == {("C", 11.611)}
        assert by_name["OH2"] == {("O", 15.599)}
        assert "Ds" not in set(u.atoms.elements)
        assert report.pseudo_particles == 14
        # every bond to a pseudo particle is gone, the real ones stay
        pseudo = set(report.pseudo_indices)
        assert not any(int(a) in pseudo or int(b) in pseudo
                       for a, b in u.atoms.bonds.indices)
        assert report.pseudo_bonds_removed == 2 * 4 + 2 * 2 + 2
        assert len(u.atoms.bonds) == 2 * 5 + 2 * 3

    def test_pdb_only_no_ds_and_no_guessed_pseudo_bonds(self):
        """PDB-only fallback (7596011): no masses/types/bonds — bonds are
        guessed (mdval item 1) but never to a pseudo particle; DSOD is not
        darmstadtium."""
        u, report = self._repair(with_masses=False, with_types=False,
                                 with_bonds=False)
        assert "Ds" not in set(u.atoms.elements)
        pseudo = set(report.pseudo_indices)
        assert _pseudo_names(u, pseudo) == PSEUDO_NAMES
        assert all(not str(u.atoms[i].element) for i in pseudo)
        assert len(u.atoms.bonds) > 0
        assert not any(int(a) in pseudo or int(b) in pseudo
                       for a, b in u.atoms.bonds.indices)

    @pytest.mark.parametrize("pdb_only", [False, True])
    def test_one_predicate_after_repair(self, pdb_only):
        """Every particle repair found satisfies the shared predicate the
        RDKit builders use (mass < 0.5, no element) and no real atom does."""
        from src_new.loader.repair import is_pseudo_particle
        kw = dict(with_masses=False, with_types=False, with_bonds=False) if pdb_only else {}
        u = _drude_system(**kw)
        if pdb_only:  # a PDB load carries name-guessed masses
            u.guess_TopologyAttrs(to_guess=["masses"])
        report = TopologyRepair(u, RunConfig()).run()
        pseudo = set(report.pseudo_indices)
        flagged = {a.index for a in u.atoms if is_pseudo_particle(a.mass, a.element)}
        assert flagged == pseudo

    def test_name_guard(self):
        r = TopologyRepair(_drude_system(), RunConfig())
        assert r._guess_single_element("", "OM", None, None) == ""
        assert r._guess_single_element("", "OM", 0.0, None, mass_trusted=True) == ""
        assert r._guess_single_element("", "OM", 15.999, None, mass_trusted=True) == "O"
        # Drude ion particle in a two-atom SOD residue: never Ds
        assert r._guess_single_element(
            "", "DSOD", None, None, resname="SOD", residue_atom_count=2,
            mass_trusted=False) != "Ds"


def _facade(u, report=None):
    return LoadedUniverse(universe=u, decision=SimpleNamespace(),
                          repair_report=report or SimpleNamespace(), results=None)


def _signatures(frag):
    from src_new.signatures.generators._perceive_cache import clear_cache
    from src_new.signatures.generators.inchi import InchiKeyGenerator
    from src_new.signatures.generators.selfies import SelfiesGenerator
    from src_new.signatures.generators.skeleton_fp import SkeletonFingerprintGenerator
    from src_new.signatures.generators.smiles import (
        SimpleSmilesGenerator, SimpleSmilesGeneratorNoSanitize)
    from tests.src_new.signatures.test_skeleton_fp_generator import _make_facade
    clear_cache()
    cfg = SignaturesConfig()
    gens = (SimpleSmilesGenerator(cfg), SimpleSmilesGeneratorNoSanitize(cfg),
            InchiKeyGenerator(cfg), SelfiesGenerator(cfg),
            SkeletonFingerprintGenerator(cfg))
    return {g.name: g.generate(MagicMock(), frag, _make_facade()) for g in gens}


class TestFacadeAndSignatures:
    @pytest.mark.parametrize("pdb_only", [False, True])
    def test_fragments_and_signatures_without_pseudo(self, pdb_only):
        kw = dict(with_masses=False, with_types=False, with_bonds=False) if pdb_only else {}
        u = _drude_system(**kw)
        report = TopologyRepair(u, RunConfig()).run()
        facade = _facade(u, report)
        pseudo = set(report.pseudo_indices)
        segs = sorted(facade.get_segments())
        for seg in segs:
            frag = facade.get_fragment(seg)
            assert not pseudo & {int(i) for i in frag.indices}, seg
            assert all(str(e) for e in frag.elements), seg

        meoh = facade.get_fragment("MEMB")
        from src_new.signatures.generators._perceive_cache import real_atoms
        assert real_atoms(meoh) is meoh  # nothing left for the builders to strip
        assert sorted(meoh.names) == sorted(["CB", "OG", "HG1", "HB1", "HB2", "HB3"])
        inst = facade.extract_molecule_instance("MEMB")
        assert inst.element_composition == {"C": 1, "O": 1, "H": 4}
        assert inst.copy_number == 2
        sig = _signatures(meoh)
        assert sig["inchi_key"] == METHANOL_KEY, sig
        assert all(sig[k] for k in ("smiles", "smiles_not_sanitized", "selfies",
                                    "skeleton_fp")), sig

        water = facade.extract_molecule_instance("TIP3")
        assert water.element_composition == {"O": 1, "H": 2}
        assert str(water.molecule_type).lower().endswith("water")
        assert _signatures(facade.get_fragment("TIP3"))["inchi_key"] == WATER_KEY

        # ions: one real atom per residue, Na and Cl
        ion_elems = sorted(str(facade.get_fragment(s).elements[0])
                           for s in segs if s.startswith("IONS"))
        assert ion_elems == ["Cl", "Na"]
        assert all(len(facade.get_fragment(s)) == 1
                   for s in segs if s.startswith("IONS"))

    def test_facade_without_repair_report_detects_pseudo(self):
        """Facades built without a repair run (tests, tools) detect them too."""
        u = _drude_system()
        u.add_TopologyAttr("elements", [
            "" if str(n) in PSEUDO_NAMES else
            {"CB": "C", "OG": "O", "OH2": "O", "SOD": "Na", "CLA": "Cl"}.get(str(n), "H")
            for n in u.atoms.names])
        facade = _facade(u)
        frag = facade.get_fragment("MEMB")
        assert len(frag) == 6
        assert facade.get_segment_properties("MEMB").atom_count_fragment == 6

    def test_selectors_keep_every_universe_atom(self):
        """Pseudo particles stay in the universe: the system export still
        writes them (atom indices unchanged)."""
        u = _drude_system()
        n = len(u.atoms)
        TopologyRepair(u, RunConfig()).run()
        assert len(u.atoms) == n


class TestPsfPdbNameTruncation:
    def test_names_match(self):
        from src_new.loader.strategies import _atom_names_match
        assert _atom_names_match("DC210", "DC21")
        assert _atom_names_match("HB1", "1HB")
        assert not _atom_names_match("DC210", "DC22")
        assert not _atom_names_match("C210", "C21")  # both fit 4 columns
        assert not _atom_names_match("C2", "C21")

    def test_check_accepts_truncated_pdb_names(self, tmp_path):
        from src_new.loader.strategies import (
            _GateFailure, _check_topology_structure_names)
        u = Universe.empty(3, n_residues=1, n_segments=1,
                           atom_resindex=[0, 0, 0], trajectory=True)
        u.add_TopologyAttr("names", ["C210", "DC210", "H10R"])
        pdb = tmp_path / "s.pdb"

        def _write(names):
            pdb.write_text("".join(
                f"ATOM  {i + 1:5d} {nm:<4s} POPCM{1:4d}    "
                f"{float(i):8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{0.0:6.2f}      MEMB\n"
                for i, nm in enumerate(names)) + "END\n")

        _write(["C210", "DC21", "H10R"])
        _check_topology_structure_names(u, pdb)  # accepted: no exception
        _write(["C210", "DC22", "H10R"])
        with pytest.raises(_GateFailure):
            _check_topology_structure_names(u, pdb)


def _tip4p_box(n=3):
    names = ["OW", "HW1", "HW2", "MW"] * n
    u = Universe.empty(4 * n, n_residues=n, n_segments=1,
                       atom_resindex=[i // 4 for i in range(4 * n)],
                       residue_segindex=[0] * n, trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resnames", ["SOL"] * n)
    u.add_TopologyAttr("resids", list(range(1, n + 1)))
    u.add_TopologyAttr("segids", ["SOL"])
    u.add_TopologyAttr("masses", [15.9994, 1.008, 1.008, 0.0] * n)
    u.add_TopologyAttr("bonds", [(4 * k + a, 4 * k + b) for k in range(n) for a, b in ((0, 1), (0, 2))])
    pos = [np.add(xyz, (5.0 * (i // 4), 0, 0)) for i, xyz in
           enumerate([(0, 0, 0), (0.96, 0, 0), (-0.24, 0.93, 0), (0.1, 0.1, 0)] * n)]
    u.load_new(np.array(pos, dtype=np.float32)[np.newaxis], format="memory")
    return u


def test_no_notice_for_plain_four_site_water():
    # every TIP4P box has massless MW sites: not worth a note on each run
    from src_new.pipeline_steps import _only_water_sites
    u = _tip4p_box()
    report = TopologyRepair(u, RunConfig()).run()
    assert report.pseudo_particles == 3 and _only_water_sites(u, report)
    drude = _drude_system()
    assert not _only_water_sites(drude, TopologyRepair(drude, RunConfig()).run())
