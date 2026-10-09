"""Probe layer + AMBER coordinate-source coverage (loading-strategy widening, Phase 2).

Covers: topology-free n_atoms probing (defer semantics for static/mdcrd sources),
atom-count mismatch -> structured `rejected_atoms` attempts, AMBER rst7/mdcrd
decision + validation + loading, GROMACS_TPR_TRR fallback presence, and honest
failures for topology-less deposits. Fixtures under tests/data/ (make_fixtures.py).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

mdanalysis = pytest.importorskip("MDAnalysis")
import MDAnalysis as mda

from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.input.models import InputKind
from src_new.loader.probe import match_atoms, probe_source_n_atoms
from src_new.loader.strategies import (
    LoadStrategy,
    get_fallback_strategies,
    load_simulation,
    validate_for_strategy,
)
from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager

try:
    import rdkit  # noqa: F401
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RST7_DIR = DATA_DIR / "amber_prmtop_rst7"
MDCRD_DIR = DATA_DIR / "amber_prmtop_mdcrd"
DCD_DIR = DATA_DIR / "charmm_psf_dcd"
PSF_PDB_DIR = DATA_DIR / "charmm_psf_pdb"
N_ATOMS = 36


class TestProbe:
    """Topology-free coordinate-source probing."""

    def test_probe_dcd_header(self):
        assert probe_source_n_atoms(DCD_DIR / "traj.dcd") == N_ATOMS

    def test_probe_mdcrd_defers(self):
        """AMBER ascii .mdcrd: TRJReader needs n_atoms upfront -> probe defers."""
        assert probe_source_n_atoms(MDCRD_DIR / "traj.mdcrd") is None

    def test_probe_static_pdb_not_applicable(self):
        assert probe_source_n_atoms(PSF_PDB_DIR / "system.pdb") is None

    def test_probe_broken_dcd_defers(self, tmp_path: Path):
        broken = tmp_path / "broken.dcd"
        broken.write_text("not a dcd file at all")
        assert probe_source_n_atoms(broken) is None

    def test_match_equal(self):
        r = match_atoms(N_ATOMS, DCD_DIR / "traj.dcd")
        assert r.ok and r.error_code == "" and r.n_atoms_source == N_ATOMS

    def test_match_mismatch_reports_both_counts(self):
        r = match_atoms(30, DCD_DIR / "traj.dcd")
        assert not r.ok
        assert r.error_code == "rejected_atoms"
        assert r.n_atoms_source == N_ATOMS and r.n_atoms_topology == 30
        assert "30" in r.error_message and str(N_ATOMS) in r.error_message

    def test_match_static_source_is_ok(self):
        r = match_atoms(N_ATOMS, PSF_PDB_DIR / "system.pdb")
        assert r.ok and r.error_code == ""

    def test_match_probe_failed_is_defer_not_fail(self, tmp_path: Path):
        broken = tmp_path / "broken.dcd"
        broken.write_text("garbage")
        r = match_atoms(N_ATOMS, broken)
        assert r.ok and r.error_code == "probe_failed"


class TestAmberDiscovery:
    def test_rst7_decision(self):
        dec = select_best_file_combination(inspect_directory(RST7_DIR))
        assert dec.input_kind == InputKind.AMBER
        assert dec.selected_strategy == "PRMTOP_RST7"

    def test_mdcrd_decision(self):
        dec = select_best_file_combination(inspect_directory(MDCRD_DIR))
        assert dec.input_kind == InputKind.AMBER
        assert dec.selected_strategy == "PRMTOP_MDCRD"

    def test_prmtop_only_is_honest_unknown(self, tmp_path: Path):
        d = tmp_path / "prmtop_only"
        d.mkdir()
        shutil.copy(RST7_DIR / "system.prmtop", d / "system.prmtop")
        dec = select_best_file_combination(inspect_directory(d))
        assert dec.input_kind is None
        assert dec.selected_strategy == "UNKNOWN"


class TestAmberStrategyWiring:
    def test_validate_rst7(self):
        v = validate_for_strategy(inspect_directory(RST7_DIR), LoadStrategy.AMBER_PRMTOP_RST7)
        assert v.ok and "prmtop" in v.selected_files and "rst7" in v.selected_files

    def test_validate_mdcrd(self):
        v = validate_for_strategy(inspect_directory(MDCRD_DIR), LoadStrategy.AMBER_PRMTOP_MDCRD)
        assert v.ok and "prmtop" in v.selected_files and "mdcrd" in v.selected_files

    def test_fallback_pruning(self):
        bundle = inspect_directory(RST7_DIR)
        dec = select_best_file_combination(bundle)
        strats = get_fallback_strategies(dec, bundle)
        assert strats[0] == LoadStrategy.AMBER_PRMTOP_RST7
        # absent coordinate formats are pruned
        assert LoadStrategy.AMBER_PRMTOP_MDCRD not in strats
        assert LoadStrategy.AMBER_PRMTOP_NC not in strats
        assert LoadStrategy.AMBER_PRMTOP_XTC not in strats

    def test_gromacs_tpr_trr_backstop_when_trr_present(self, tmp_path: Path):
        d = tmp_path / "gromacs_trr"
        d.mkdir()
        (d / "run.tpr").touch()
        (d / "run.trr").touch()
        bundle = inspect_directory(d)
        dec = select_best_file_combination(bundle)
        assert dec.input_kind == InputKind.GROMACS
        strats = get_fallback_strategies(dec, bundle)
        assert strats[0] == LoadStrategy.GROMACS_TPR
        assert LoadStrategy.GROMACS_TPR_TRR in strats


class TestAmberLoading:
    @pytest.mark.parametrize(
        "dirname,expected",
        [
            ("amber_prmtop_rst7", LoadStrategy.AMBER_PRMTOP_RST7),
            ("amber_prmtop_mdcrd", LoadStrategy.AMBER_PRMTOP_MDCRD),
        ],
    )
    def test_load_simulation(self, dirname, expected, tmp_path: Path):
        bundle = inspect_directory(DATA_DIR / dirname)
        dec = select_best_file_combination(bundle)
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert result.success, [a.error_message for a in result.attempts]
        assert result.final_strategy == expected
        assert result.universe.atoms.n_atoms == N_ATOMS


class TestProbeIntegration:
    def test_mismatched_psf_dcd_rejected_atoms(self, tmp_path: Path):
        """psf(36) vs dcd(30) -> attempt rejected with both counts, no load."""
        dep = tmp_path / "baddep"
        dep.mkdir()
        shutil.copy(PSF_PDB_DIR / "system.psf", dep / "system.psf")
        u30 = mda.Universe(str(DATA_DIR / "charmm_psf_pdb_mismatch" / "bad.pdb"))
        with mda.coordinates.DCD.DCDWriter(str(dep / "traj.dcd"), n_atoms=30) as w:
            w.write(u30)
        bundle = inspect_directory(dep)
        dec = select_best_file_combination(bundle)
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert not result.success
        codes = [a.error_code for a in result.attempts]
        assert "rejected_atoms" in codes
        rej = next(a for a in result.attempts if a.error_code == "rejected_atoms")
        assert "36" in rej.error_message and "30" in rej.error_message
        # probe also persisted into the results attempt table
        attempts = ResultsManager(tmp_path / "r.json").get_data("loading/attempts")
        assert any(a.get("error_code") == "rejected_atoms" for a in attempts)

    def test_dcd_only_deposit_fails_honestly(self, tmp_path: Path):
        dep = tmp_path / "dcd_only"
        dep.mkdir()
        shutil.copy(DCD_DIR / "traj.dcd", dep / "traj.dcd")
        bundle = inspect_directory(dep)
        dec = select_best_file_combination(bundle)
        assert dec.selected_strategy == "UNKNOWN"
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert not result.success
        assert len(result.attempts) > 0  # every strategy's validation failure recorded


class TestAmberE2E:
    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_pipeline_prmtop_rst7(self, tmp_path: Path):
        from src_new import PipelineExecutor, ResultsManager, build_load_and_export_tasks

        results = ResultsManager(tmp_path / "results.json", pipeline_name="amber_rst7_e2e")
        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=results,
            pipeline_name="amber_rst7_e2e",
        )
        executor.run(
            working_directory=RST7_DIR,
            output_directory=tmp_path / "output",
            input_kind="amber",
        )
        payload = results.as_dict()
        assert payload["pipeline"]["status"] == "success", payload["pipeline"].get("warnings")
        assert payload["pipeline"]["input_kind"] == "amber"
        assert results.get_data("loading/final_strategy") == LoadStrategy.AMBER_PRMTOP_RST7.value
        assert (tmp_path / "output" / "system.mmcif").exists()
