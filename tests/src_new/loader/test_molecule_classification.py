"""Segment molecule-type classification (v3.140, V-36).

Regression wave: run a5b785cc/b4813beb (PE_CL membrane) typed TOCL2 and POPE
as `unknown` and TIP3 water as `small_molecule`. Root causes:
 (a) nested-if blind spot: C>10,O>4 molecules with C/O outside (1,3) matched
     the outer branch and fell through every verdict (phospholipids and
     cardiolipins have C/O ~ 4.5-5);
 (b) water detection hard-coded three resnames ("SOL","HOH","WAT") while real
     force fields use TIP3/SPC/OPC families.
Grounding values (tests/data/gromacs_tpr_only probe): TOCL2 C81/O17/P2,
POPE C39/O8/P1/N1, TIP3 fragment = 1O+2H.
"""

from __future__ import annotations

import types
from pathlib import Path

import pytest

mda = pytest.importorskip("MDAnalysis")

from src_new.config.loader import RunConfig
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.fragment_store import FragmentStore
from src_new.loader.repair import TopologyRepair
from src_new.loader.strategies import load_simulation
from src_new.loader.universe_facade import LoadedUniverse
from src_new.molecules.instances import MoleculeType
from src_new.results.results_manager import ResultsManager

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
TPR_ONLY_DIR = DATA_DIR / "gromacs_tpr_only"


def _props(**kw):
    base = {"flags": {}, "atom_count_fragment": 10}
    base.update(kw)
    return types.SimpleNamespace(**base)


def _fragment(resnames, elements):
    return types.SimpleNamespace(
        residues=types.SimpleNamespace(resnames=resnames),
        atoms=types.SimpleNamespace(elements=elements),
    )


class TestClassificationDecisionList:
    """Direct _classify_molecule_type cases (no MDAnalysis needed)."""

    def _cls(self, **kw):
        return LoadedUniverse._classify_molecule_type(kw["props"], kw["frag"])

    def test_protein_flag_wins(self):
        assert self._cls(props=_props(flags={"is_protein": True}),
                         frag=_fragment(["ALA"], ["C"] * 10)) == MoleculeType.PROTEIN

    def test_nucleic_flag_wins_over_composition(self):
        # wave-7 guard: DNA C/O ~2.4 must not hit the lipid band
        assert self._cls(props=_props(flags={"is_nucleic": True}, atom_count_fragment=100),
                         frag=_fragment(["DT"], ["C"] * 50 + ["O"] * 20)) == MoleculeType.NUCLEIC

    def test_monoatomic_is_ion(self):
        assert self._cls(props=_props(atom_count_fragment=1),
                         frag=_fragment(["SOD"], ["Na"])) == MoleculeType.ION

    def test_cardiolipin_tocl2_is_lipid_via_resname(self):
        assert self._cls(props=_props(atom_count_fragment=248),
                         frag=_fragment(["TOCL2"], ["C"] * 81 + ["O"] * 17 + ["P"] * 2)) == MoleculeType.LIPID

    def test_pope_is_lipid_via_resname(self):
        assert self._cls(props=_props(atom_count_fragment=125),
                         frag=_fragment(["POPE"], ["C"] * 39 + ["O"] * 8 + ["P"] * 1)) == MoleculeType.LIPID

    def test_tip3_water_via_resname(self):
        assert self._cls(props=_props(atom_count_fragment=3),
                         frag=_fragment(["TIP3"], ["O", "H", "H"])) == MoleculeType.WATER

    def test_exotic_water_name_structural_fallback(self):
        # unknown resname, but 1O+2H => water (covers OP3 etc. not in the table)
        assert self._cls(props=_props(atom_count_fragment=3),
                         frag=_fragment(["XYZ"], ["O", "H", "H"])) == MoleculeType.WATER

    def test_legacy_glycerol_band_still_lipid(self):
        # glycerol-like C/O ~2.5 within legacy band (no resname knowledge)
        assert self._cls(props=_props(atom_count_fragment=40),
                         frag=_fragment(["LIG"], ["C"] * 25 + ["O"] * 10)) == MoleculeType.LIPID

    def test_phospholipid_band_covers_out_of_legacy_range(self):
        # unknown phospholipid resname: C/O 5 with P => lipid via P-band
        assert self._cls(props=_props(atom_count_fragment=100),
                         frag=_fragment(["XYZL"], ["C"] * 40 + ["O"] * 8 + ["P"] * 1)) == MoleculeType.LIPID

    def test_p_bearing_molecule_never_carbohydrate(self):
        # TOCL2-shape composition WITHOUT resname knowledge was historically
        # misclassifiable into the sugar band: P must exclude carbohydrate.
        assert self._cls(props=_props(atom_count_fragment=248),
                         frag=_fragment(["XYZC"], ["C"] * 81 + ["O"] * 17 + ["P"] * 2)) == MoleculeType.LIPID

    def test_o_rich_non_lipid_keeps_legacy_band_verdict(self):
        # Parity/documentation case: an O-rich mid-size molecule (sugar-like
        # C22O10) hits the legacy 1<C/O<3 band and yields LIPID. That verdict
        # predates v3.140 (the nested-if bug left it standing); we preserve it
        # rather than invent new sugar typing from the same broken band.
        assert self._cls(props=_props(atom_count_fragment=32),
                         frag=_fragment(["SUG"], ["C"] * 22 + ["O"] * 10)) == MoleculeType.LIPID

    def test_small_molecule_default(self):
        assert self._cls(props=_props(atom_count_fragment=5),
                         frag=_fragment(["MN2"], ["C", "N"])) == MoleculeType.SMALL_MOLECULE

    def test_mid_range_without_p_is_not_lipid(self):
        # C/O 4.5 without P and without lipid resname => small molecule
        # (P-band intentionally guarded; factual UNKNOWN beats invented lipid)
        assert self._cls(props=_props(atom_count_fragment=54),
                         frag=_fragment(["XYZ"], ["C"] * 45 + ["O"] * 10)) == MoleculeType.SMALL_MOLECULE


class TestRealFixtureTypes:
    """End-to-end on the committed PE_CL tpr (run a5b785cc specimen)."""

    def test_pe_cl_types_after_load_and_repair(self, tmp_path: Path):
        cfg = RunConfig()
        bundle = inspect_directory(TPR_ONLY_DIR)
        dec = select_best_file_combination(bundle)
        res = ResultsManager(tmp_path / "r.json")
        lr = load_simulation(dec, bundle, cfg, res)
        rep = TopologyRepair(lr.universe, cfg).run()
        facade = LoadedUniverse(
            universe=lr.universe, decision=dec, repair_report=rep, results=res,
            enhanced_nucleic_recognition=cfg.signatures.enhanced_nucleic_acid_recognition,
        )
        store = FragmentStore(facade, res)
        types = {i.segment_ids[0]: i.molecule_type for i in store.get_all_instances()}
        assert types["seg_0_TOCL2"] == MoleculeType.LIPID
        assert types["seg_1_POPE"] == MoleculeType.LIPID
        assert types["seg_2_TIP3"] == MoleculeType.WATER
        assert types["seg_3_SOD"] == MoleculeType.ION
