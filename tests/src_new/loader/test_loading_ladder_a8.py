"""W3 A8 (BH-016/BH-041): topology-aware loading ladder.

Production evidence (mdpc corpus): discovery had AMBER branches only for
prmtop + xtc/nc/mdcrd/rst7, so `{prmtop, pdb}` fell to PDB_SINGLE — all 8
MDposit AMBER cases (M01..M17) ran as flat PDB and lost topology charges,
atom types and bonds (M13: charge 0 instead of -3). S27's mismatched GRO
was silently dropped.

Fix contract pinned here:
1. `{prmtop, pdb}` and `{top, pdb}` load topology + STRUCTURE (new
   strategies), not the flat-PDB path.
2. `{prmtop, pdb, xtc}` still takes the trajectory step when counts match;
   when the trajectory atom count differs the run continues WITHOUT it
   with a `trajectory_ignored` warning (never a failure) and loads
   topology + structure.
3. Falling back to a structure-only strategy while a topology file was
   in the bundle records a `topology_ignored` warning (S27 gro mismatch).
4. loading/ladder records {strategy, outcome, reason} per step.
5. Same answer either way: a topology family must yield identical
   segments with and without the trajectory (M13: prmtop+pdb vs
   prmtop+pdb+matching-xtc).
"""

from __future__ import annotations

import shutil
import warnings
from pathlib import Path

import numpy as np
import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")
import MDAnalysis as mda

from src_new.config.loader import RunConfig
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import load_simulation
from src_new.results.results_manager import ResultsManager

DATA = Path(__file__).resolve().parents[2] / "data"
M13_DIR = Path(
    "/home/tomsko/work/bat3_article_reviews/bioid_bughunt/testcases/"
    "M13_daptomycin_amber/input")


def _bundle_dir(tmp_path: Path, files: dict[str, Path]) -> Path:
    d = tmp_path / "input"
    d.mkdir(parents=True, exist_ok=True)
    for name, src in files.items():
        shutil.copy(src, d / name)
    return d


def _pdb_from_universe(u, out: Path, n_atoms: int | None = None) -> Path:
    """Write a PDB for the first n atoms of a universe (topology-free
    structure step fixture)."""
    ag = u.atoms if n_atoms is None else u.atoms[:n_atoms]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ag.write(str(out))
    return out


def _xtc_from_universe(u, out: Path, n_atoms: int | None = None) -> Path:
    from MDAnalysis.coordinates.memory import MemoryReader
    if n_atoms is not None:
        pos = u.atoms.positions[:n_atoms]
    else:
        pos = u.atoms.positions
    arr = pos[np.newaxis, :, :].astype(np.float32)
    seg = mda.Universe.empty(arr.shape[1], trajectory=True)
    seg.load_new(arr, format="memory")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with mda.Writer(str(out), seg.atoms.n_atoms) as w:
            w.write(seg)
    return out


def _load(tmp_path: Path, bundle_dir: Path):
    results = ResultsManager(str(tmp_path / "results.json"), pipeline_name="a8")
    from src_new.results.results_manager import ResultsManager as RM  # noqa
    decision = select_best_file_combination(inspect_directory(bundle_dir))
    res = load_simulation(decision=decision, bundle=inspect_directory(bundle_dir),
                          config=RunConfig(), results=results)
    return res, results


class TestAmberPrmtopPdb:
    def test_prmtop_pdb_loads_as_amber_topology(self, tmp_path):
        src = DATA / "amber_prmtop_rst7"
        u_full = mda.Universe(str(src / "system.prmtop"),
                              str(src / "coords.rst7"), format="RESTRT")
        pdb = _pdb_from_universe(u_full, tmp_path / "structure.pdb")
        d = _bundle_dir(tmp_path, {"topology.prmtop": src / "system.prmtop",
                                   "structure.pdb": pdb})
        res, results = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "amber_prmtop_pdb", (
            res.final_strategy)
        # topology won: charges come from the prmtop, not from flat-PDB zeros
        assert abs(float(res.universe.atoms.charges.sum())
                   - float(u_full.atoms.charges.sum())) < 1e-3
        assert abs(float(u_full.atoms.charges.sum())) > 0.01  # fixture really charged
        assert res.universe.atoms.n_atoms == u_full.atoms.n_atoms
        # ladder record present and names the winning strategy
        ladder = results.get_data("loading/ladder")
        assert ladder, "loading/ladder must record every step"
        last = ladder[-1]
        assert last["strategy"] == "amber_prmtop_pdb"
        assert last["outcome"] == "success"

    def test_prmtop_pdb_xtc_prefers_trajectory_when_counts_match(self, tmp_path):
        src = DATA / "amber_prmtop_rst7"
        u_full = mda.Universe(str(src / "system.prmtop"),
                              str(src / "coords.rst7"), format="RESTRT")
        d = _bundle_dir(tmp_path, {
            "topology.prmtop": src / "system.prmtop",
            "structure.pdb": _pdb_from_universe(u_full, tmp_path / "structure.pdb"),
            "md.xtc": _xtc_from_universe(u_full, tmp_path / "md.xtc"),
        })
        res, results = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "amber_prmtop_xtc"
        assert results.get_data("loading/warnings") is None or \
            not any("trajectory_ignored" in w
                    for w in (results.get_data("loading/warnings") or []))

    def test_stripped_xtc_falls_back_to_structure_with_warning(self, tmp_path):
        """Trajectory atom count mismatch must NEVER fail the run: drop it
        with a trajectory_ignored warning, load topology+structure."""
        src = DATA / "amber_prmtop_rst7"
        u_full = mda.Universe(str(src / "system.prmtop"),
                              str(src / "coords.rst7"), format="RESTRT")
        d = _bundle_dir(tmp_path, {
            "topology.prmtop": src / "system.prmtop",
            "structure.pdb": _pdb_from_universe(u_full, tmp_path / "structure.pdb"),
            "md.xtc": _xtc_from_universe(u_full, tmp_path / "md.xtc",
                                         n_atoms=u_full.atoms.n_atoms - 40),
        })
        res, results = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "amber_prmtop_pdb", (
            res.final_strategy, [a.error_message for a in res.attempts])
        warnings_ = results.get_data("loading/warnings") or []
        assert any("trajectory_ignored" in w for w in warnings_), warnings_
        # topology still won: prmtop charges present
        assert abs(float(res.universe.atoms.charges.sum())) > 0.01


class TestGromacsTopologyPdb:
    def test_top_pdb_loads_as_gromacs_topology(self, tmp_path):
        src = DATA / "16319"
        top = src / "topol.top"
        gro = src / "md.gro"
        if not (top.exists() and gro.exists()):
            pytest.skip("16319 fixture absent")
        u_full = mda.Universe(str(top), str(gro), topology_format="ITP",
                              infer_system=True)
        pdb = _pdb_from_universe(u_full, tmp_path / "structure.pdb")
        # NOTE: no .gro on disk -> topology + structure step must engage
        d = _bundle_dir(tmp_path, {"topol.top": top, "structure.pdb": pdb})
        for itp in src.glob("*.itp"):
            shutil.copy(itp, d / itp.name)
        res, results = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value in ("gromacs_top_pdb",
                                            "gromacs_itp_pdb"), res.final_strategy
        assert res.universe.atoms.n_atoms == u_full.atoms.n_atoms

    def test_tpr_gro_mismatch_drops_gro_with_warning(self, tmp_path):
        """BH-041/S27: mismatched GRO must not be silently dropped — ladder
        record + warning, run continues on the TPR (its own coordinates)."""
        src = DATA / "gromacs_tpr_gro"
        tpr = src / "PE_CL_530Run.tpr"
        gro_full = mda.Universe(str(tpr), str(src / "PE_CL_530Run.gro"))
        bad_gro = _pdb_from_universe(  # wrong-count .gro written from pdb layout
            gro_full, tmp_path / "bad.gro", n_atoms=gro_full.atoms.n_atoms - 20)
        d = _bundle_dir(tmp_path, {"topol.tpr": tpr,
                                   "bad.gro": bad_gro})
        res, results = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "gromacs_tpr", res.final_strategy
        warnings_ = results.get_data("loading/warnings") or []
        assert any("topology_ignored" in w or "coordinate_source_ignored" in w
                   for w in warnings_), warnings_
        ladder = results.get_data("loading/ladder") or []
        assert any(a.get("outcome") == "failed" for a in ladder), ladder


@pytest.mark.skipif(not (M13_DIR / "topology.prmtop").exists(),
                    reason="M13 fixture not present")
class TestSameAnswerWithAndWithoutTrajectory:
    def test_m13_segments_and_charge_match(self, tmp_path):
        """The 8-case AMBER acceptance: prmtop+pdb and prmtop+pdb+xtc give
        the same system — same atoms, same net charge (-3 for M13), same
        segment set."""
        prmtop = M13_DIR / "topology.prmtop"
        pdb = M13_DIR / "structure.pdb"
        u_ref = mda.Universe(str(prmtop), str(pdb),
                             topology_format="PRMTOP", format="PDB")
        # bundle A: topology + structure
        dA = _bundle_dir(tmp_path / "a", {"topology.prmtop": prmtop,
                                          "structure.pdb": pdb})
        # bundle B: + a count-matching dummy trajectory
        dB = _bundle_dir(tmp_path / "b", {
            "topology.prmtop": prmtop,
            "structure.pdb": pdb,
            "md.xtc": _xtc_from_universe(u_ref, tmp_path / "md.xtc"),
        })
        resA, _ = _load(tmp_path / "a", dA)
        resB, _ = _load(tmp_path / "b", dB)
        assert resA.success and resB.success
        assert resA.final_strategy.value == "amber_prmtop_pdb"
        assert resB.final_strategy.value == "amber_prmtop_xtc"
        assert resA.universe.atoms.n_atoms == resB.universe.atoms.n_atoms
        qA = float(resA.universe.atoms.charges.sum())
        qB = float(resB.universe.atoms.charges.sum())
        assert int(round(qA)) == -3, qA  # M13 topology charge — the BH-016 loss
        assert int(round(qB)) == -3, qB


class TestStructureAloneFiTail:
    """User condition (A8 review): the structure-file-alone tail must be
    exercised explicitly, with the failure REASON visible in the ladder."""

    def test_broken_include_top_pdb_falls_to_flat_pdb(self, tmp_path):
        """{top, pdb} with a broken force-field #include: the GROMACS
        topology step fails, the deposit loads as flat PDB, the ladder
        records the ITPParser failure and topology_ignored carries the
        reason (A-16 shape, new explicit contract)."""
        d = tmp_path / "input"
        d.mkdir()
        (d / "topol.top").write_text(
            '#include "amber99sb-ildn.ff/forcefield.itp"\n[ system ]\nt\n')
        (d / "structure.pdb").write_text(
            'ATOM      1  N   ALA X   1      11.104   6.134  10.000  1.00 20.00           N\nATOM      2  CA  ALA X   1      12.560   6.300  10.000  1.00 20.00           C\nATOM      3  C   ALA X   1      13.000   7.700  10.000  1.00 20.00           C\nATOM      4  O   ALA X   1      12.400   8.700  10.000  1.00 20.00           O\nEND\n')
        bundle = inspect_directory(d)
        decision = select_best_file_combination(bundle)
        assert decision.selected_strategy == "TOP_PDB"
        results = ResultsManager(str(tmp_path / "results.json"),
                                 pipeline_name="a8")
        res = load_simulation(decision=decision, bundle=bundle,
                              config=RunConfig(), results=results)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "pdb"
        ladder = results.get_data("loading/ladder")
        failed = [e for e in ladder if e["outcome"] != "success"]
        assert any(e["strategy"].startswith("gromacs_")
                   and "ITPParser" in e.get("error_message", "")
                   for e in failed), ladder
        warnings_ = results.get_data("loading/warnings")
        assert any("topology_ignored" in w for w in warnings_), warnings_

    def test_broken_psf_falls_to_flat_pdb(self, tmp_path):
        """CHARMM pair: an unparseable .psf next to a loadable .pdb must
        degrade to flat PDB with topology_ignored (same tail as AMBER)."""
        d = tmp_path / "input"
        d.mkdir()
        (d / "system.psf").write_bytes(b"\x00\x01not-a-psf-at-all")
        (d / "structure.pdb").write_text(
            'ATOM      1  N   ALA X   1      11.104   6.134  10.000  1.00 20.00           N\nATOM      2  CA  ALA X   1      12.560   6.300  10.000  1.00 20.00           C\nATOM      3  C   ALA X   1      13.000   7.700  10.000  1.00 20.00           C\nATOM      4  O   ALA X   1      12.400   8.700  10.000  1.00 20.00           O\nEND\n')
        bundle = inspect_directory(d)
        decision = select_best_file_combination(bundle)
        from src_new.input.models import InputKind
        assert decision.input_kind == InputKind.CHARMM
        results = ResultsManager(str(tmp_path / "results.json"),
                                 pipeline_name="a8")
        res = load_simulation(decision=decision, bundle=bundle,
                              config=RunConfig(), results=results)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "pdb"
        warnings_ = results.get_data("loading/warnings")
        assert any("topology_ignored" in w for w in warnings_), warnings_


def _dcd_from_positions(pos, out: Path) -> Path:
    arr = np.asarray(pos, dtype=np.float32)[np.newaxis, :, :]
    seg = mda.Universe.empty(arr.shape[1], trajectory=True)
    seg.load_new(arr, format="memory")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with mda.Writer(str(out), seg.atoms.n_atoms) as w:
            w.write(seg)
    return out


class TestSolventStrippedTrajectory:
    """g1 (2026-11-05): MDposit serves trajectory.xtc with water and
    counter-ions removed while the topology keeps the full solvated
    system (entry 9333: parm7 14,671 atoms, xtc 76). With no static
    structure in the bundle every such run failed load_failed/
    atom_count_mismatch (~400 corpus entries). The pairing now retries,
    as the LAST resort, against solvent-stripped subsets of the topology
    with a bond-length sanity gate."""

    SRC = DATA / "charmm_psf_dcd"  # 28 solute atoms, then 2 TIP3 + SOD + CLA
    # the synthetic fixture's bonds are stretched (median 2.4 A); scaled
    # to atomistic lengths so the bond-length gate sees real chemistry
    SCALE = 0.6

    def _full(self):
        u = mda.Universe(str(self.SRC / "system.psf"),
                         str(self.SRC / "traj.dcd"))
        u.atoms.positions = u.atoms.positions * self.SCALE
        return u

    def test_stripped_dcd_loads_solute_with_topology(self, tmp_path):
        u = self._full()
        k = 28
        assert set(u.atoms[k:].resnames) <= {"TIP3", "SOD", "CLA"}
        d = _bundle_dir(tmp_path, {
            "system.psf": self.SRC / "system.psf",
            "traj.dcd": _dcd_from_positions(u.atoms.positions[:k],
                                            tmp_path / "traj.dcd")})
        res, results = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "charmm_psf_dcd"
        assert res.universe.atoms.n_atoms == k
        assert list(res.universe.atoms.names) == list(u.atoms[:k].names)
        np.testing.assert_allclose(res.universe.atoms.positions,
                                   u.atoms.positions[:k], atol=1e-3)
        # topology metadata survives (charges, bonds)
        np.testing.assert_allclose(res.universe.atoms.charges,
                                   u.atoms[:k].charges, atol=1e-6)
        assert len(res.universe.bonds) > 0
        warnings_ = results.get_data("loading/warnings") or []
        assert any(w.startswith("trajectory_solvent_stripped") for w in warnings_), warnings_
        assert not any(w.startswith("trajectory_ignored") for w in warnings_), warnings_
        info = results.get_data("loading/stripped_trajectory")
        assert info["subset"] == "prefix" and info["n_topology"] == 36

    def test_scrambled_coordinates_fail_the_bond_gate(self, tmp_path):
        """Right count, wrong mapping: the bond-length gate rejects it and
        the run still reports atom_count_mismatch (no silent mis-load)."""
        rng = np.random.default_rng(0)
        pos = rng.uniform(0, 40, size=(28, 3))
        d = _bundle_dir(tmp_path, {
            "system.psf": self.SRC / "system.psf",
            "traj.dcd": _dcd_from_positions(pos, tmp_path / "traj.dcd")})
        res, results = _load(tmp_path, d)
        assert not res.success
        summary = results.get_data("loading/failure_summary")
        assert summary["reason"] == "atom_count_mismatch", summary

    def test_count_matching_no_subset_still_fails(self, tmp_path):
        u = self._full()
        d = _bundle_dir(tmp_path, {
            "system.psf": self.SRC / "system.psf",
            "traj.dcd": _dcd_from_positions(u.atoms.positions[:20],
                                            tmp_path / "traj.dcd")})
        res, results = _load(tmp_path, d)
        assert not res.success
        assert results.get_data("loading/failure_summary")["reason"] == \
            "atom_count_mismatch"


class TestBlankAmberAtomTypes:
    """g1 (2026-11-05): 54 corpus prmtops (MDposit MD-A001AH family) ship
    an AMBER_ATOM_TYPE section that is present but blank; MDAnalysis
    rejected the whole topology ("Expect: 1077 Have: 0")."""

    def _blank_types(self, src: Path, out: Path) -> Path:
        lines = src.read_text().splitlines()
        i = next(k for k, ln in enumerate(lines)
                 if ln.startswith("%FLAG AMBER_ATOM_TYPE"))
        j = next(k for k in range(i + 2, len(lines))
                 if lines[k].startswith("%"))
        lines[i + 2:j] = [" " * 80] * (j - i - 2)
        out.write_text("\n".join(lines) + "\n")
        return out

    def test_blank_types_load_with_element_types(self, tmp_path):
        src = DATA / "amber_prmtop_rst7"
        u_ref = mda.Universe(str(src / "system.prmtop"),
                             str(src / "coords.rst7"), format="RESTRT")
        blank = self._blank_types(src / "system.prmtop",
                                  tmp_path / "blank.prmtop")
        with pytest.raises(Exception):
            mda.Universe(str(blank), topology_format="PRMTOP")
        d = _bundle_dir(tmp_path, {
            "system.prmtop": blank,
            "md.xtc": _xtc_from_universe(u_ref, tmp_path / "md.xtc")})
        res, results = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "amber_prmtop_xtc"
        u = res.universe
        assert u.atoms.n_atoms == u_ref.atoms.n_atoms
        np.testing.assert_allclose(u.atoms.charges, u_ref.atoms.charges)
        assert len(u.bonds) == len(u_ref.bonds)
        # types are element symbols of ATOMIC_NUMBER (the synthetic
        # fixture stores mass numbers there, so only shape is checked)
        assert all(t.strip() for t in u.atoms.types) and len(set(u.atoms.types)) > 1
        warnings_ = results.get_data("loading/warnings") or []
        assert any(w.startswith("prmtop_atom_types_filled") for w in warnings_)
        # the attempt table still names the deposited file, not the copy
        assert any(p.endswith("system.prmtop") and str(tmp_path) in p
                   for a in res.attempts for p in a.used_files)

    def test_intact_prmtop_is_untouched(self, tmp_path):
        from src_new.loader.strategies import _prmtop_with_atom_types
        assert _prmtop_with_atom_types(
            DATA / "amber_prmtop_rst7" / "system.prmtop") is None


class TestGromacsTopologyTrajectory:
    """g1 (2026-11-05): {topology.top, trajectory.xtc} bundles (36 corpus
    entries, + 8 {*.itp, xtc}) had no strategy at all; every one failed
    validation_failed ("No .tpr files found"). The MDposit topology is
    solvated (2071: 136,320 atoms) and the trajectory solvent-stripped
    (12,584), so the new pairing goes through the same atom-count probe
    and solvent-stripped retry as the AMBER/CHARMM trajectory pairs."""

    SRC = DATA / "16319"  # DPPC bilayer: 72 DPPC, then SOL + Na/Cl

    def _bundle(self, tmp_path, n_atoms=None):
        top, gro = self.SRC / "topol.top", self.SRC / "md.gro"
        if not (top.exists() and gro.exists()):
            pytest.skip("16319 fixture absent")
        u = mda.Universe(str(top), str(gro), topology_format="ITP",
                         infer_system=True)
        files = {p.name: p for p in self.SRC.glob("*.itp")}
        files["topol.top"] = top
        files["traj.xtc"] = _xtc_from_universe(u, tmp_path / "traj.xtc",
                                               n_atoms=n_atoms)
        return u, _bundle_dir(tmp_path, files)

    def test_discovery_picks_top_xtc(self, tmp_path):
        _u, d = self._bundle(tmp_path)
        decision = select_best_file_combination(inspect_directory(d))
        assert decision.selected_strategy == "TOP_XTC"

    def test_full_trajectory_loads(self, tmp_path):
        u, d = self._bundle(tmp_path)
        res, results = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "gromacs_top_xtc"
        assert res.universe.atoms.n_atoms == u.atoms.n_atoms
        assert not any(w.startswith("trajectory_")
                       for w in (results.get_data("loading/warnings") or []))

    def test_solvent_stripped_trajectory_loads_solute(self, tmp_path):
        u_full = mda.Universe(str(self.SRC / "topol.top"),
                              str(self.SRC / "md.gro"), topology_format="ITP",
                              infer_system=True)
        k = int((u_full.atoms.resnames == "DPPC").sum())
        assert set(u_full.atoms[k:].resnames) <= {"SOL", "Na", "Cl"}
        u, d = self._bundle(tmp_path, n_atoms=k)
        res, results = _load(tmp_path, d)
        assert res.success, [a.error_message for a in res.attempts]
        assert res.final_strategy.value == "gromacs_top_xtc"
        assert res.universe.atoms.n_atoms == k
        assert set(res.universe.residues.resnames) == {"DPPC"}
        info = results.get_data("loading/stripped_trajectory")
        assert info["subset"] == "prefix" and info["n_topology"] == u.atoms.n_atoms
