"""mmCIF loading coverage — matrix completeness row (gemmi->PDB->Universe).

Note: MDAnalysis has no native CIF parser; the strategy converts via gemmi.
gemmi >= 0.7 dropped Structure.num_models() — a compat shim keeps the strategy
working on current gemmi (covered by test_load below).
"""

from __future__ import annotations

from pathlib import Path

import pytest

mdanalysis = pytest.importorskip("MDAnalysis")
gemmi = pytest.importorskip("gemmi")

from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.input.models import InputKind
from src_new.loader.strategies import LoadStrategy, load_simulation
from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager

try:
    import rdkit  # noqa: F401
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
MMCIF_DIR = DATA_DIR / "mmcif_single"
N_ATOMS = 36


class TestMmcifLoading:
    def test_decision(self):
        dec = select_best_file_combination(inspect_directory(MMCIF_DIR))
        assert dec.input_kind == InputKind.MMCIF
        assert dec.selected_strategy == "MMCIF_SINGLE"

    def test_load(self, tmp_path: Path):
        bundle = inspect_directory(MMCIF_DIR)
        dec = select_best_file_combination(bundle)
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert result.success, [a.error_message for a in result.attempts]
        assert result.final_strategy == LoadStrategy.MMCIF_GEMMI
        assert result.universe.atoms.n_atoms == N_ATOMS


class TestMmcifE2E:
    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_pipeline_mmcif(self, tmp_path: Path):
        from src_new import PipelineExecutor, ResultsManager, build_load_and_export_tasks

        results = ResultsManager(tmp_path / "results.json", pipeline_name="mmcif_e2e")
        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=results,
            pipeline_name="mmcif_e2e",
        )
        executor.run(
            working_directory=MMCIF_DIR,
            output_directory=tmp_path / "output",
            input_kind="mmcif",
        )
        payload = results.as_dict()
        assert payload["pipeline"]["status"] == "success", payload["pipeline"].get("warnings")
        assert results.get_data("loading/final_strategy") == LoadStrategy.MMCIF_GEMMI.value
        assert (tmp_path / "output" / "system.mmcif").exists()
