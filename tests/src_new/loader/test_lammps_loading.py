"""LAMMPS .data loading coverage (loading-strategy widening, Phase 4).

.data carries topology + coordinates in one file; atom styles vary by deposit,
so the strategy trusts the file's own "Atoms # <style>" declaration first and
then retries common styles. Near-empty catalogs are a VALID success for LAMMPS
deposits (they often carry no residue nomenclature — locked empty-catalog
semantic from Phase 3).
"""

from __future__ import annotations

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
    _load_lammps_data,
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
LAMMPS_DIR = DATA_DIR / "lammps_data"
N_ATOMS = 36


class TestLammpsDiscovery:
    def test_data_detected_as_lammps(self):
        assert discover_input_kind(LAMMPS_DIR) == InputKind.LAMMPS

    def test_decision(self):
        dec = select_best_file_combination(inspect_directory(LAMMPS_DIR))
        assert dec.input_kind == InputKind.LAMMPS
        assert dec.selected_strategy == "DATA_SINGLE"
        assert dec.topology_files and dec.topology_files[0].name == "system.data"


class TestLammpsStrategy:
    def test_validate(self):
        v = validate_for_strategy(inspect_directory(LAMMPS_DIR), LoadStrategy.LAMMPS_DATA)
        assert v.ok and "data" in v.selected_files

    def test_fallback_exactly_lammps_data(self):
        bundle = inspect_directory(LAMMPS_DIR)
        dec = select_best_file_combination(bundle)
        assert get_fallback_strategies(dec, bundle) == [LoadStrategy.LAMMPS_DATA]

    def test_load(self, tmp_path: Path):
        bundle = inspect_directory(LAMMPS_DIR)
        dec = select_best_file_combination(bundle)
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert result.success, [a.error_message for a in result.attempts]
        assert result.final_strategy == LoadStrategy.LAMMPS_DATA
        assert result.universe.atoms.n_atoms == N_ATOMS
        assert result.universe.atoms.positions[0][0] == pytest.approx(1.0, abs=1e-3)


class TestLammpsAtomStyleRetry:
    def test_broken_data_compiles_all_sub_attempts(self, tmp_path: Path):
        """Structurally unparseable under every style -> records every try."""
        bad = tmp_path / "bad.data"
        bad.write_text("LAMMPS data file\n\n    1 atoms\n\nbroken rows, no sections\n")
        with pytest.raises(RuntimeError) as exc_info:
            _load_lammps_data(bad)
        msg = str(exc_info.value)
        assert "atom styles" in msg
        assert "<file-declared>" in msg
        assert "full" in msg or "id resid type q x y z" in msg

    def test_honest_failure_recorded(self, tmp_path: Path):
        dep = tmp_path / "lammps_bad"
        dep.mkdir()
        (dep / "sys.data").write_bytes(b"LAMMPS data file\n\n 1 atoms\n\nbroken\n")
        bundle = inspect_directory(dep)
        dec = select_best_file_combination(bundle)
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert not result.success
        assert any(a.error_code == "load_exception" for a in result.attempts)


class TestLammpsE2E:
    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_pipeline_lammps_data(self, tmp_path: Path):
        """Near-empty catalog is a valid success (Phase-3 semantic), so assert
        pipeline health + provenance, not catalog contents."""
        from src_new import PipelineExecutor, ResultsManager, build_load_and_export_tasks

        results = ResultsManager(tmp_path / "results.json", pipeline_name="lammps_e2e")
        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=results,
            pipeline_name="lammps_e2e",
        )
        executor.run(
            working_directory=LAMMPS_DIR,
            output_directory=tmp_path / "output",
            input_kind="lammps",
        )
        payload = results.as_dict()
        assert payload["pipeline"]["status"] == "success", payload["pipeline"].get("warnings")
        assert payload["pipeline"]["input_kind"] == "lammps"
        assert results.get_data("loading/final_strategy") == LoadStrategy.LAMMPS_DATA.value
        molecules = results.get_data("molecules")
        assert molecules is not None and molecules.get("count", 0) >= 0
