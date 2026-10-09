from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

# Skip all tests if MDAnalysis is missing
mdanalysis = pytest.importorskip("MDAnalysis")

from src_new.loader.strategies import (
    LoadStrategy,
    validate_for_strategy,
    get_fallback_strategies,
    load_with_strategy,
    load_simulation,
    FileValidation,
    LoadingResult,
)
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.input.models import InputKind, InputBundle, LoadDecision, FileRecord
from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager


# Test data paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_16319 = DATA_DIR / "16319"  # GROMACS TOP+GRO + many .itp files
DATA_1010142 = DATA_DIR / "1010142"  # GROMACS TOP+GRO
DATA_35193_A = DATA_DIR / "35193_a"  # GROMACS TPR+GRO
DATA_14976_A = DATA_DIR / "14976_a"  # GROMACS TPR-only
DATA_14976 = DATA_DIR / "14976"  # GROMACS multiple TPRs (no GRO)


class TestValidateForStrategy:
    """Tests for validate_for_strategy function."""

    def test_validate_gromacs_tpr_gro_finds_single_files(self):
        """Test validation for GROMACS_TPR_GRO strategy with single files."""
        bundle = inspect_directory(DATA_35193_A)
        validation = validate_for_strategy(bundle, LoadStrategy.GROMACS_TPR_GRO)
        
        assert validation.ok is True
        assert len(validation.errors) == 0
        assert "tpr" in validation.selected_files
        assert "gro" in validation.selected_files
        assert validation.selected_files["tpr"].suffix == ".tpr"
        assert validation.selected_files["gro"].suffix == ".gro"

    def test_validate_gromacs_top_gro(self):
        """Test validation for GROMACS_TOP_GRO strategy."""
        bundle = inspect_directory(DATA_16319)
        validation = validate_for_strategy(bundle, LoadStrategy.GROMACS_TOP_GRO)
        
        assert validation.ok is True
        assert len(validation.errors) == 0
        assert "top" in validation.selected_files
        assert "gro" in validation.selected_files

    def test_validate_gromacs_tpr_only(self):
        """Test validation for GROMACS_TPR strategy with single TPR."""
        bundle = inspect_directory(DATA_14976_A)
        validation = validate_for_strategy(bundle, LoadStrategy.GROMACS_TPR)
        
        assert validation.ok is True
        assert len(validation.errors) == 0
        assert len(validation.warnings) == 0
        assert "tpr" in validation.selected_files
        assert validation.selected_files["tpr"].suffix == ".tpr"

    def test_validate_warns_on_multiple_tpr(self):
        """Test validation warns on multiple TPR files and picks alphabetically first."""
        bundle = inspect_directory(DATA_14976)
        validation = validate_for_strategy(bundle, LoadStrategy.GROMACS_TPR)
        
        assert validation.ok is True  # Still loadable
        assert "multiple_tpr_files" in validation.warnings
        assert "tpr" in validation.selected_files
        # Should be alphabetically first: 100.tpr
        assert validation.selected_files["tpr"].name == "100.tpr"

    def test_validate_fails_missing_gro(self):
        """Test validation fails when GRO is missing for TPR_GRO strategy."""
        bundle = inspect_directory(DATA_14976_A)  # Has TPR, no GRO
        validation = validate_for_strategy(bundle, LoadStrategy.GROMACS_TPR_GRO)
        
        assert validation.ok is False
        assert len(validation.errors) > 0
        assert any("gro" in err.lower() for err in validation.errors)


class TestGetFallbackStrategies:
    """Tests for get_fallback_strategies function."""

    def test_fallback_strategies_tpr_only(self):
        """Test fallback strategies for TPR_ONLY decision."""
        bundle = inspect_directory(DATA_14976_A)
        decision = LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TPR_ONLY",
            topology_files=[list(DATA_14976_A.glob("*.tpr"))[0]],
        )
        strategies = get_fallback_strategies(decision, bundle)
        
        # TPR_ONLY should start with GROMACS_TPR
        assert strategies[0] == LoadStrategy.GROMACS_TPR

    def test_fallback_strategies_filters_invalid(self):
        """Test that fallback strategies filters out invalid strategies."""
        bundle = inspect_directory(DATA_14976_A)  # TPR only, no GRO
        decision = LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TPR_ONLY",
            topology_files=[list(DATA_14976_A.glob("*.tpr"))[0]],
        )
        strategies = get_fallback_strategies(decision, bundle)
        
        # GROMACS_TPR_GRO should be filtered out (no GRO file)
        # GROMACS_TOP_GRO should be filtered out (no TOP file)
        # GROMACS_ITP_GRO should be filtered out (no ITP or GRO)
        # Only GROMACS_TPR should remain
        assert LoadStrategy.GROMACS_TPR in strategies
        assert LoadStrategy.GROMACS_TPR_GRO not in strategies


class TestLoadWithStrategy:
    """Tests for load_with_strategy function."""

    def test_load_gromacs_tpr_gro(self):
        """Test loading with GROMACS_TPR_GRO strategy."""
        bundle = inspect_directory(DATA_35193_A)
        validation = validate_for_strategy(bundle, LoadStrategy.GROMACS_TPR_GRO)
        assert validation.ok is True
        
        config = RunConfig()
        universe = load_with_strategy(LoadStrategy.GROMACS_TPR_GRO, validation.selected_files, config)
        
        assert universe is not None
        assert len(universe.atoms) > 0

    def test_load_gromacs_top_gro(self):
        """Test loading with GROMACS_TOP_GRO strategy."""
        bundle = inspect_directory(DATA_16319)
        validation = validate_for_strategy(bundle, LoadStrategy.GROMACS_TOP_GRO)
        assert validation.ok is True
        
        config = RunConfig()
        universe = load_with_strategy(LoadStrategy.GROMACS_TOP_GRO, validation.selected_files, config)
        
        assert universe is not None
        assert len(universe.atoms) > 0

    def test_load_gromacs_tpr_only(self):
        """Test loading with GROMACS_TPR strategy."""
        bundle = inspect_directory(DATA_14976_A)
        validation = validate_for_strategy(bundle, LoadStrategy.GROMACS_TPR)
        assert validation.ok is True
        
        config = RunConfig()
        universe = load_with_strategy(LoadStrategy.GROMACS_TPR, validation.selected_files, config)
        
        assert universe is not None
        assert len(universe.atoms) > 0

    def test_load_pdb_from_temp(self):
        """Test loading a minimal PDB file."""
        # Create a minimal PDB file
        pdb_content = """HEADER    TEST
ATOM      1  N   ALA A   1      20.153  22.867   4.981  1.00 18.40           N
ATOM      2  CA  ALA A   1      20.250  24.321   5.050  1.00 17.20           C
ATOM      3  C   ALA A   1      21.732  24.680   5.200  1.00 16.80           C
ATOM      4  O   ALA A   1      22.401  23.890   5.890  1.00 15.90           O
TER
END
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as tmp:
            tmp.write(pdb_content)
            tmp_path = Path(tmp.name)
        
        try:
            # Create a minimal bundle
            record = FileRecord.from_path(tmp_path, "file_000000", "PDB", "structure")
            bundle = InputBundle(root_directory=tmp_path.parent, files=[record])
            
            validation = validate_for_strategy(bundle, LoadStrategy.PDB)
            assert validation.ok is True
            
            config = RunConfig()
            universe = load_with_strategy(LoadStrategy.PDB, validation.selected_files, config)
            
            assert universe is not None
            assert len(universe.atoms) == 4
        finally:
            tmp_path.unlink()


class TestLoadSimulation:
    """Tests for load_simulation orchestrator function."""

    def test_load_simulation_records_attempts(self):
        """Test that load_simulation records attempts to results."""
        bundle = inspect_directory(DATA_35193_A)
        # Use TPR_GRO decision to get gromacs_tpr_gro as first strategy
        decision = LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TPR_GRO",
            topology_files=[list(DATA_35193_A.glob("*.tpr"))[0]],
        )
        config = RunConfig()
        
        # Create temp results manager
        with tempfile.TemporaryDirectory() as tmpdir:
            results_path = Path(tmpdir) / "results.json"
            manager = ResultsManager(results_path)
            
            result = load_simulation(decision, bundle, config, manager)
            
            assert result.success is True
            assert result.final_strategy is not None
            assert len(result.attempts) >= 1
            
            # Check results were recorded
            assert manager.get_data("loading/success") is True
            # With TPR_GRO decision, first strategy is GROMACS_TPR_GRO
            assert manager.get_data("loading/final_strategy") == "gromacs_tpr_gro"
            attempts = manager.get_data("loading/attempts")
            assert attempts is not None
            assert len(attempts) >= 1

    def test_load_simulation_with_tpr_only_decision(self):
        """Test load_simulation with TPR_ONLY decision on TPR+GRO data."""
        bundle = inspect_directory(DATA_35193_A)
        # Force TPR_ONLY decision even though GRO is available
        decision = LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TPR_ONLY",
            topology_files=[list(DATA_35193_A.glob("*.tpr"))[0]],
        )
        config = RunConfig()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            results_path = Path(tmpdir) / "results.json"
            manager = ResultsManager(results_path)
            
            result = load_simulation(decision, bundle, config, manager)

            # Contract: TPR preferred, but ONLY if its coordinates are readable.
            # Environments whose MDAnalysis build cannot read coords from these
            # TPRs (UserWarning "No coordinate reader found") make GROMACS_TPR
            # fail the no_positions gate -> GROMACS_TPR_GRO must supply coords.
            assert result.success is True
            assert result.final_strategy in (LoadStrategy.GROMACS_TPR, LoadStrategy.GROMACS_TPR_GRO)
            if result.final_strategy == LoadStrategy.GROMACS_TPR:
                assert result.universe.atoms.positions is not None
                assert manager.get_data("loading/final_strategy") == "gromacs_tpr"

    def test_load_simulation_failure_records_all_attempts(self):
        """Test that load_simulation records all failed attempts."""
        # Use data that will fail for most strategies
        bundle = inspect_directory(DATA_14976_A)  # TPR only
        decision = LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="TOP_GRO",  # Wrong strategy - will fail validation
            topology_files=[],
        )
        config = RunConfig()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            results_path = Path(tmpdir) / "results.json"
            manager = ResultsManager(results_path)
            
            result = load_simulation(decision, bundle, config, manager)

            # TPR-only fixture with a wrong initial decision.
            # Environments with working TPR coordinate readers: succeeds via
            # GROMACS_TPR. Environments without (pre-existing install quirk,
            # see TestFacade14976a baseline): GROMACS_TPR is rejected by the
            # no_positions gate and the deposit fails honestly.
            attempts = manager.get_data("loading/attempts")
            assert attempts is not None
            if result.success:
                assert result.final_strategy == LoadStrategy.GROMACS_TPR
            else:
                # proper failure path: gate rejection recorded with the code
                codes = [a.get("error_code") for a in attempts]
                assert "no_positions" in codes


class TestLoadingResult:
    """Tests for LoadingResult dataclass."""

    def test_loading_result_default_values(self):
        """Test LoadingResult default values."""
        result = LoadingResult(success=False)
        
        assert result.success is False
        assert result.universe is None
        assert result.final_strategy is None
        assert result.attempts == []
        assert result.warnings == []


class TestFileValidation:
    """Tests for FileValidation dataclass."""

    def test_file_validation_default_values(self):
        """Test FileValidation default values."""
        validation = FileValidation(ok=True)
        
        assert validation.ok is True
        assert validation.warnings == []
        assert validation.errors == []
        assert validation.selected_files == {}
