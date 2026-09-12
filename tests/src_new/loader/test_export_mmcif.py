from __future__ import annotations

import pytest
import json
import numpy as np

mdanalysis = pytest.importorskip("MDAnalysis")
biopython = pytest.importorskip("Bio")

from pathlib import Path
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import load_simulation
from src_new.loader.repair import TopologyRepair, RepairReport
from src_new.loader.universe_facade import LoadedUniverse
from src_new.loader.export_mmcif import export_system_mmcif, export_segment_mmcif
from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager
from src_new.input.models import LoadDecision, InputKind


def _make_minimal_universe(n_atoms=4, with_dimensions=False):
    """Create a minimal in-memory universe for fast testing.
    
    Args:
        n_atoms: Number of atoms (default 4)
        with_dimensions: If True, set unit cell dimensions
        
    Returns:
        MDAnalysis.Universe with basic topology and positions
    """
    from MDAnalysis import Universe
    from MDAnalysis.coordinates.memory import MemoryReader
    
    # Create empty universe with 1 residue, 1 segment
    u = Universe.empty(n_atoms, n_residues=1, n_segments=1,
                       atom_resindex=[0] * n_atoms,
                       residue_segindex=[0],
                       trajectory=True)
    
    # Add per-atom attrs
    u.add_TopologyAttr('names', [f"AT{i}" for i in range(n_atoms)])
    u.add_TopologyAttr('types', ["C", "H", "O", "N"][:n_atoms])
    u.add_TopologyAttr('elements', ["C", "H", "O", "N"][:n_atoms])
    u.add_TopologyAttr('resids', [1])
    u.add_TopologyAttr('resnames', ["RES"])
    u.add_TopologyAttr('segids', ["SYSTEM"])
    
    # Add positions
    positions = np.array([[0, 0, 0], [1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]], dtype=np.float32)[:n_atoms]
    u.load_new(positions, format='memory')
    
    # Optionally set dimensions
    if with_dimensions:
        u.dimensions = [10.0, 10.0, 10.0, 90.0, 90.0, 90.0]
    
    return u


def _make_minimal_universe_two_segments(n_atoms_per_seg=4, with_dimensions=False):
    """Create a minimal in-memory universe with two segments.
    
    Args:
        n_atoms_per_seg: Number of atoms per segment
        with_dimensions: If True, set unit cell dimensions
        
    Returns:
        MDAnalysis.Universe with two segments
    """
    from MDAnalysis import Universe
    import numpy as np
    
    n_atoms = n_atoms_per_seg * 2
    
    # Create empty universe with 2 residues, 2 segments
    # atoms 0-3 in residue 0, atoms 4-7 in residue 1
    # residue 0 in segment 0, residue 1 in segment 1
    u = Universe.empty(n_atoms, n_residues=2, n_segments=2,
                       atom_resindex=[0] * n_atoms_per_seg + [1] * n_atoms_per_seg,
                       residue_segindex=[0, 1],
                       trajectory=True)
    
    # Add per-atom attrs
    names = [f"AT{i}" for i in range(n_atoms)]
    types = ["C", "H", "O", "N"] * 2
    elements = ["C", "H", "O", "N"] * 2
    u.add_TopologyAttr('names', names)
    u.add_TopologyAttr('types', types)
    u.add_TopologyAttr('elements', elements)
    
    # Add per-residue attrs
    u.add_TopologyAttr('resids', [1, 2])
    u.add_TopologyAttr('resnames', ["RES1", "RES2"])
    
    # Add per-segment attrs
    u.add_TopologyAttr('segids', ["SEG1", "SEG2"])
    
    # Add positions
    positions = np.array([[i, 0, 0] for i in range(n_atoms)], dtype=np.float32)
    u.load_new(positions, format='memory')
    
    if with_dimensions:
        u.dimensions = [12.0, 12.0, 12.0, 90.0, 90.0, 90.0]
    
    return u


class MinimalFacade:
    """Minimal facade for testing export functions.
    
    Provides only the attributes/methods needed by export_system_mmcif
    and export_segment_mmcif: universe and get_segments().
    """
    
    def __init__(self, universe):
        self.universe = universe
    
    def get_segments(self) -> set[str]:
        return set(self.universe.segments.segids)


def _make_lightweight_facade(tmp_path: Path, with_dimensions=True, two_segments=False):
    """Create a lightweight facade for fast testing.
    
    Args:
        tmp_path: pytest tmp_path fixture
        with_dimensions: If True, set unit cell dimensions
        two_segments: If True, create universe with two segments
        
    Returns:
        tuple: (MinimalFacade, ResultsManager)
    """
    if two_segments:
        u = _make_minimal_universe_two_segments(with_dimensions=with_dimensions)
    else:
        u = _make_minimal_universe(with_dimensions=with_dimensions)
    
    facade = MinimalFacade(u)
    results = ResultsManager(tmp_path / "results.json")
    
    return facade, results


# =============================================================================
# Fast tests for cell parameter injection (no real GROMACS files)
# =============================================================================

class TestExportMmcifCellParameters:
    """Fast tests verifying _cell.* records are written when dimensions exist."""
    
    def test_system_export_includes_cell(self, tmp_path: Path):
        """Test that system export includes cell parameters when dimensions are set."""
        facade, results = _make_lightweight_facade(tmp_path, with_dimensions=True)
        output = tmp_path / "system.mmcif"
        
        result = export_system_mmcif(facade, output, results)
        
        assert result.exists()
        content = result.read_text()
        
        # Assert cell parameters are present
        assert "_cell.length_a" in content
        assert "_cell.length_b" in content
        assert "_cell.length_c" in content
        assert "_cell.angle_alpha" in content
        assert "_cell.angle_beta" in content
        assert "_cell.angle_gamma" in content
        assert "_symmetry.space_group_name_H-M" in content
    
    def test_system_export_without_cell(self, tmp_path: Path):
        """Test that system export omits cell parameters when dimensions are not set."""
        facade, results = _make_lightweight_facade(tmp_path, with_dimensions=False)
        output = tmp_path / "system.mmcif"
        
        result = export_system_mmcif(facade, output, results)
        
        assert result.exists()
        content = result.read_text()
        
        # Assert cell parameters are NOT present
        assert "_cell.length_a" not in content
        assert "_cell.length_b" not in content
        assert "_cell.length_c" not in content
        assert "_cell.angle_alpha" not in content
        assert "_cell.angle_beta" not in content
        assert "_cell.angle_gamma" not in content
    
    def test_segment_export_includes_cell(self, tmp_path: Path):
        """Test that segment export includes cell parameters when dimensions are set."""
        facade, results = _make_lightweight_facade(tmp_path, with_dimensions=True, two_segments=True)
        output = tmp_path / "segment.mmcif"
        
        result = export_segment_mmcif(facade, "SEG1", output, results)
        
        assert result.exists()
        content = result.read_text()
        
        # Assert cell parameters are present
        assert "_cell.length_a" in content
        assert "_cell.length_b" in content
        assert "_cell.length_c" in content
        assert "_cell.angle_alpha" in content
        assert "_cell.angle_beta" in content
        assert "_cell.angle_gamma" in content
        assert "_symmetry.space_group_name_H-M" in content
    
    def test_segment_export_without_cell(self, tmp_path: Path):
        """Test that segment export omits cell parameters when dimensions are not set."""
        facade, results = _make_lightweight_facade(tmp_path, with_dimensions=False, two_segments=True)
        output = tmp_path / "segment.mmcif"
        
        result = export_segment_mmcif(facade, "SEG1", output, results)
        
        assert result.exists()
        content = result.read_text()
        
        # Assert cell parameters are NOT present
        assert "_cell.length_a" not in content
        assert "_cell.length_b" not in content
        assert "_cell.length_c" not in content
        assert "_cell.angle_alpha" not in content
        assert "_cell.angle_beta" not in content
        assert "_cell.angle_gamma" not in content


# =============================================================================
# Heavy tests with real GROMACS data (marked slow)
# =============================================================================

def _make_facade(data_dir: str, tmp_path: Path):
    """Create a LoadedUniverse facade from real data files.
    
    This is slow as it loads real GROMACS TPR files.
    """
    root = Path(data_dir)
    bundle = inspect_directory(root)
    decision = select_best_file_combination(bundle)
    
    results = ResultsManager(tmp_path / "results.json")
    config = RunConfig()
    config.loader.guess_missing_elements = True
    config.loader.guess_missing_masses = True
    config.loader.guess_missing_bonds = True
    
    load_result = load_simulation(decision, bundle, config, results)
    assert load_result.success
    
    repair = TopologyRepair(load_result.universe, config)
    repair_report = repair.run()
    
    facade = LoadedUniverse(load_result.universe, decision, repair_report, results)
    return facade, results


@pytest.mark.slow
class TestExportSystemMmcif:
    def test_exports_system_file(self, tmp_path: Path):
        facade, results = _make_facade("tests/data/14976_a", tmp_path)
        output = tmp_path / "system.mmcif"
        
        result = export_system_mmcif(facade, output, results)
        
        assert result.exists()
        assert result.stat().st_size > 0
        content = result.read_text()
        assert "loop_" in content or "ATOM" in content
        
        # Assert cell parameters are present when universe has dimensions
        try:
            has_dimensions = facade.universe.dimensions is not None
        except AttributeError:
            has_dimensions = False
        if has_dimensions:
            assert "_cell.length_a" in content
            assert "_cell.length_b" in content
            assert "_cell.length_c" in content
            assert "_cell.angle_alpha" in content
            assert "_cell.angle_beta" in content
            assert "_cell.angle_gamma" in content
            assert "_symmetry.space_group_name_H-M" in content

    def test_records_artifact(self, tmp_path: Path):
        facade, results = _make_facade("tests/data/14976_a", tmp_path)
        output = tmp_path / "system.mmcif"
        export_system_mmcif(facade, output, results)
        
        payload = results.as_dict()
        assert "artifacts" in payload
        assert len(payload["artifacts"]) > 0
        artifact = next(iter(payload["artifacts"].values()))
        assert artifact["kind"] == "mmcif"

    def test_records_data_path(self, tmp_path: Path):
        facade, results = _make_facade("tests/data/14976_a", tmp_path)
        output = tmp_path / "system.mmcif"
        export_system_mmcif(facade, output, results)
        
        assert results.get_data("exports/system_mmcif") == str(output)


@pytest.mark.slow
class TestExportSegmentMmcif:
    def test_exports_segment_file(self, tmp_path: Path):
        facade, results = _make_facade("tests/data/16319", tmp_path)
        output = tmp_path / "segment.sol.mmcif"
        
        # Segment names follow pattern {RESNAME}_{NUMBER}, e.g., "SOL_1"
        result = export_segment_mmcif(facade, "SOL_1", output, results)
        
        assert result.exists()
        content = result.read_text()
        assert "SOL" in content or "ATOM" in content
        
        # Assert cell parameters are present when universe has dimensions
        try:
            has_dimensions = facade.universe.dimensions is not None
        except AttributeError:
            has_dimensions = False
        if has_dimensions:
            assert "_cell.length_a" in content
            assert "_cell.length_b" in content
            assert "_cell.length_c" in content
            assert "_cell.angle_alpha" in content
            assert "_cell.angle_beta" in content
            assert "_cell.angle_gamma" in content
            assert "_symmetry.space_group_name_H-M" in content

    def test_records_segment_data(self, tmp_path: Path):
        facade, results = _make_facade("tests/data/14976_a", tmp_path)
        output = tmp_path / "popc.mmcif"
        export_segment_mmcif(facade, "seg_0_POPC", output, results)
        
        assert "popc.mmcif" in results.get_data("exports/segment_mmcif/seg_0_POPC")
