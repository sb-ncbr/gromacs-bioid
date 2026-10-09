"""CHARMM/NAMD loading coverage (loading-strategy widening, Phase 1).

Covers discovery (kind detection, {psf,pdb} -> CHARMM precedence over the
generic PDB branch, psf-only honest-failure decision), strategy validation /
fallback ordering, direct loading of the three synthetic CHARMM deposits, and
full load-and-export e2e for psf+pdb and psf+dcd (the latter proving that
frame-0-from-DCD universes work end-to-end with in_memory=False).

Fixtures are committed under tests/data/ (regenerate via make_fixtures.py).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

mdanalysis = pytest.importorskip("MDAnalysis")

from src_new.input.discovery import (
    discover_input_kind,
    inspect_directory,
    select_best_file_combination,
)
from src_new.input.models import InputKind
from src_new.loader.strategies import (
    LoadStrategy,
    get_fallback_strategies,
    load_simulation,
    load_with_strategy,
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
PSF_PDB_DIR = DATA_DIR / "charmm_psf_pdb"
PSF_CRD_DIR = DATA_DIR / "charmm_psf_crd"
PSF_DCD_DIR = DATA_DIR / "charmm_psf_dcd"
N_ATOMS = 36


def _load(dir_path: Path, tmp_path: Path):
    """discover -> decide -> load_simulation; returns (decision, result)."""
    bundle = inspect_directory(dir_path)
    decision = select_best_file_combination(bundle)
    results = ResultsManager(tmp_path / "results.json")
    config = RunConfig()
    result = load_simulation(decision, bundle, config, results)
    return bundle, decision, result, results


class TestCharmmDiscovery:
    """Kind detection and decision ladder for CHARMM deposits."""

    def test_psf_pdb_detected_as_charmm(self):
        assert discover_input_kind(PSF_PDB_DIR) == InputKind.CHARMM

    def test_psf_crd_detected_as_charmm(self):
        assert discover_input_kind(PSF_CRD_DIR) == InputKind.CHARMM

    def test_psf_dcd_detected_as_charmm(self):
        assert discover_input_kind(PSF_DCD_DIR) == InputKind.CHARMM

    def test_psf_pdb_beats_generic_pdb_branch(self):
        """{psf, pdb} deposits keep CHARMM topology, never degrade to flat PDB."""
        bundle = inspect_directory(PSF_PDB_DIR)
        decision = select_best_file_combination(bundle)
        assert decision.input_kind == InputKind.CHARMM
        assert decision.selected_strategy == "PSF_PDB"

    def test_psf_crd_prefers_crd(self):
        decision = select_best_file_combination(inspect_directory(PSF_CRD_DIR))
        assert decision.input_kind == InputKind.CHARMM
        assert decision.selected_strategy == "PSF_CRD"

    def test_psf_dcd_prefers_dcd_frame0(self):
        decision = select_best_file_combination(inspect_directory(PSF_DCD_DIR))
        assert decision.input_kind == InputKind.CHARMM
        assert decision.selected_strategy == "PSF_DCD"

    def test_psf_only_decision_warns_and_missing_topology_fails(self, tmp_path: Path):
        """psf with no coordinate source: CHARMM decision + warning; strategies
        all fail validation -> load_simulation returns honest failure."""
        d = tmp_path / "psf_only"
        d.mkdir()
        shutil.copy(PSF_PDB_DIR / "system.psf", d / "system.psf")
        bundle, decision, result, _ = _load(d, tmp_path)
        assert decision.input_kind == InputKind.CHARMM
        assert decision.selected_strategy == "PSF_ONLY"
        assert "charmm_psf_without_coordinate_source" in decision.warnings
        assert not result.success
        assert len(result.attempts) == 0 or all(a.status == "failed" for a in result.attempts)


class TestSuffixTableRoles:
    """Canonical suffix table semantics on CHARMM fixtures."""

    def test_psf_is_topology_role(self):
        bundle = inspect_directory(PSF_PDB_DIR)
        roles = {r.path.suffix.lower(): (r.file_type, r.role) for r in bundle.files}
        assert roles[".psf"] == ("CHARMM_PSF", "topology")
        assert roles[".pdb"] == ("PDB", "structure")

    def test_dcd_is_trajectory_role(self):
        bundle = inspect_directory(PSF_DCD_DIR)
        roles = {r.path.suffix.lower(): (r.file_type, r.role) for r in bundle.files}
        assert roles[".dcd"] == ("CHARMM_DCD", "trajectory")


class TestCharmmStrategyValidation:
    """validate_for_strategy + fallback ordering."""

    def test_validate_all_three_on_matching_deposits(self):
        cases = [
            (PSF_PDB_DIR, LoadStrategy.CHARMM_PSF_PDB, "pdb"),
            (PSF_CRD_DIR, LoadStrategy.CHARMM_PSF_CRD, "crd"),
            (PSF_DCD_DIR, LoadStrategy.CHARMM_PSF_DCD, "dcd"),
        ]
        for dir_path, strategy, coord_key in cases:
            bundle = inspect_directory(dir_path)
            v = validate_for_strategy(bundle, strategy)
            assert v.ok, (dir_path.name, v.errors)
            assert "psf" in v.selected_files and coord_key in v.selected_files

    def test_fallback_dcd_first_and_pruned(self):
        bundle = inspect_directory(PSF_DCD_DIR)
        decision = select_best_file_combination(bundle)
        strats = get_fallback_strategies(decision, bundle)
        assert strats[0] == LoadStrategy.CHARMM_PSF_DCD
        # pdb/crd strategies pruned when their files are absent
        assert LoadStrategy.CHARMM_PSF_PDB not in strats
        assert LoadStrategy.CHARMM_PSF_CRD not in strats

    def test_fallback_crd_first_prefers_static_over_trajectory(self):
        bundle = inspect_directory(PSF_CRD_DIR)
        decision = select_best_file_combination(bundle)
        strats = get_fallback_strategies(decision, bundle)
        assert strats[0] == LoadStrategy.CHARMM_PSF_CRD


class TestCharmmLoading:
    """Direct loading of the three CHARMM deposits."""

    @pytest.mark.parametrize(
        "dirname,expected",
        [
            ("charmm_psf_pdb", LoadStrategy.CHARMM_PSF_PDB),
            ("charmm_psf_crd", LoadStrategy.CHARMM_PSF_CRD),
            ("charmm_psf_dcd", LoadStrategy.CHARMM_PSF_DCD),
        ],
    )
    def test_load_simulation_succeeds(self, dirname, expected, tmp_path: Path):
        bundle, decision, result, _ = _load(DATA_DIR / dirname, tmp_path)
        assert result.success, [a.error_message for a in result.attempts]
        assert result.final_strategy == expected
        assert result.universe.atoms.n_atoms == N_ATOMS

    def test_dcd_frame0_positions_and_trajectory_attached(self, tmp_path: Path):
        _,_,result,_ = _load(PSF_DCD_DIR, tmp_path)
        assert result.success
        u = result.universe
        # trajectory attached, frame 0 realized, generator pos of atom 0 = (1,0,0)
        assert len(u.trajectory) == 3
        assert u.atoms.positions[0][0] == pytest.approx(1.0, abs=1e-3)
        assert u.atoms.positions[0][1] == pytest.approx(0.0, abs=1e-3)

    def test_psf_segids_preserved_no_system_collapse(self, tmp_path: Path):
        _,_,result,_ = _load(PSF_PDB_DIR, tmp_path)
        assert result.success
        segids = set(result.universe.segments.segids)
        assert {"PROA", "SOLV", "IONS"} <= segids

    def test_attempt_names_recorded(self, tmp_path: Path):
        _,_,result, results = _load(PSF_PDB_DIR, tmp_path)
        assert result.success
        attempts = results.get_data("loading/attempts")
        strategies = [a["strategy"] for a in attempts]
        assert strategies == [LoadStrategy.CHARMM_PSF_PDB.value]
        assert attempts[0]["status"] == "success"


class TestCharmmE2E:
    """Full load-and-export pipeline on CHARMM deposits."""

    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_pipeline_psf_pdb(self, tmp_path: Path):
        from src_new import PipelineExecutor, ResultsManager, build_load_and_export_tasks

        results = ResultsManager(tmp_path / "results.json", pipeline_name="charmm_psf_pdb_e2e")
        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=results,
            pipeline_name="charmm_psf_pdb_e2e",
        )
        executor.run(
            working_directory=PSF_PDB_DIR,
            output_directory=tmp_path / "output",
            input_kind="charmm",
        )
        payload = results.as_dict()
        assert payload["pipeline"]["status"] == "success", payload["pipeline"].get("warnings")
        assert payload["pipeline"]["input_kind"] == "charmm"
        assert payload["tasks"]["load_simulation"]["status"] == "success"
        assert results.get_data("loading/final_strategy") == LoadStrategy.CHARMM_PSF_PDB.value
        out = tmp_path / "output"
        assert (out / "system.mmcif").exists()
        assert (out / "PROA.mmcif").exists()

    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_pipeline_psf_dcd_frame0_no_trajectory_iteration(self, tmp_path: Path):
        """CHARMM_PSF_DCD universe (in_memory=False) must pass unwrap/analysis/export."""
        from src_new import PipelineExecutor, ResultsManager, build_load_and_export_tasks

        results = ResultsManager(tmp_path / "results.json", pipeline_name="charmm_psf_dcd_e2e")
        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=results,
            pipeline_name="charmm_psf_dcd_e2e",
        )
        executor.run(
            working_directory=PSF_DCD_DIR,
            output_directory=tmp_path / "output",
            input_kind="charmm",
        )
        payload = results.as_dict()
        assert payload["pipeline"]["status"] == "success", payload["pipeline"].get("warnings")
        assert results.get_data("loading/final_strategy") == LoadStrategy.CHARMM_PSF_DCD.value
        assert (tmp_path / "output" / "PROA.mmcif").exists()
