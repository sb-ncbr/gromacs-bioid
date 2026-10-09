"""Post-build success gates + empty-catalog semantics (Phase 3).

Gates (mdpc executor port): after a successful Universe() build, require
n_atoms > 0 (`empty_universe`) and coordinates present (`no_positions`).
Deliberately NO protein gate — solvent-only / empty-catalog deposits are a
valid success for bat3 (catalogs every molecule, not just proteins).
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

mdanalysis = pytest.importorskip("MDAnalysis")

from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import (
    LoadStrategy,
    load_simulation,
)
from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager

try:
    import rdkit  # noqa: F401
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SOLVENT_DIR = DATA_DIR / "solvent_only_pdb"
PSF_DIR = DATA_DIR / "charmm_psf_pdb"


class TestEmptyUniverseGate:
    def test_zero_atom_universe_rejected_with_empty_universe(self, tmp_path: Path):
        """Gate fires when load_with_strategy returns a 0-atom universe."""
        import MDAnalysis as mda

        dep = tmp_path / "empty"
        dep.mkdir()
        (dep / "x.pdb").write_text("HEADER    X\nEND\n")  # routes decision to PDB

        bundle = inspect_directory(dep)
        dec = select_best_file_combination(bundle)

        import src_new.loader.strategies as strategies_mod
        with mock.patch.object(strategies_mod, "load_with_strategy", return_value=mda.Universe.empty(0)):
            result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))

        assert not result.success
        codes = [a.error_code for a in result.attempts]
        assert codes == ["empty_universe"]
        # and it was persisted into the results attempt table
        attempts = ResultsManager(tmp_path / "r.json").get_data("loading/attempts")
        assert any(a.get("error_code") == "empty_universe" for a in attempts)

    def test_zero_atom_pdb_fails_at_parse_as_load_exception(self, tmp_path: Path):
        """Documents MDAnalysis behavior: a 0-atom text structure fails at PARSE
        time (IndexError) -> load_exception; the gate is a second line of defence."""
        dep = tmp_path / "empty"
        dep.mkdir()
        (dep / "empty.pdb").write_text("HEADER    NOTHING HERE\nEND\n")
        bundle = inspect_directory(dep)
        dec = select_best_file_combination(bundle)
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert not result.success
        assert "load_exception" in [a.error_code for a in result.attempts]


class TestNoPositionsGate:
    def test_coordinate_less_universe_rejected(self, tmp_path: Path):
        """A Universe without coordinates (topology-only source) is rejected."""
        import MDAnalysis as mda

        dep = tmp_path / "coordsless"
        dep.mkdir()
        (dep / "x.pdb").write_text("HEADER    X\nEND\n")  # deposits a pdb so decision routes PDB

        coordless = mda.Universe(str(PSF_DIR / "system.psf"))  # psf: topology, no positions

        bundle = inspect_directory(dep)
        dec = select_best_file_combination(bundle)

        import src_new.loader.strategies as strategies_mod
        with mock.patch.object(strategies_mod, "load_with_strategy", return_value=coordless):
            result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))

        assert not result.success
        codes = [a.error_code for a in result.attempts]
        assert codes == ["no_positions"]  # PDB is the only viable strategy here


class TestEmptyCatalogSemantics:
    @pytest.mark.skipif(not HAS_RDKIT, reason="rdkit not installed")
    def test_solvent_only_runs_full_pipeline_as_valid_success(self, tmp_path: Path):
        """solvent-only deposit: pipeline succeeds, catalog holds water only."""
        from src_new import PipelineExecutor, ResultsManager, build_load_and_export_tasks

        results = ResultsManager(tmp_path / "results.json", pipeline_name="solvent_gate_e2e")
        executor = PipelineExecutor(
            steps=build_load_and_export_tasks(),
            results_manager=results,
            pipeline_name="solvent_gate_e2e",
        )
        executor.run(
            working_directory=SOLVENT_DIR,
            output_directory=tmp_path / "output",
            input_kind="pdb",
        )
        payload = results.as_dict()
        assert payload["pipeline"]["status"] == "success", payload["pipeline"].get("warnings")
        assert results.get_data("loading/final_strategy") == LoadStrategy.PDB.value
        molecules = results.get_data("molecules")
        assert molecules and molecules["count"] >= 1
        # catalog contains nothing bio-molecular — water (solvent) entries only
        assert set(molecules["type_counts"]) <= {"water", "ion"}
