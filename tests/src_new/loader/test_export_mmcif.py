from __future__ import annotations

import pytest
import json

mdanalysis = pytest.importorskip("MDAnalysis")
biopython = pytest.importorskip("Bio")

from pathlib import Path
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import load_simulation
from src_new.loader.repair import TopologyRepair
from src_new.loader.universe_facade import LoadedUniverse
from src_new.loader.export_mmcif import export_system_mmcif, export_segment_mmcif
from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager


def _make_facade(data_dir: str, tmp_path: Path):
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


class TestExportSystemMmcif:
    def test_exports_system_file(self, tmp_path: Path):
        facade, results = _make_facade("tests/data/14976_a", tmp_path)
        output = tmp_path / "system.mmcif"
        
        result = export_system_mmcif(facade, output, results)
        
        assert result.exists()
        assert result.stat().st_size > 0
        content = result.read_text()
        assert "loop_" in content or "ATOM" in content

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


class TestExportSegmentMmcif:
    def test_exports_segment_file(self, tmp_path: Path):
        facade, results = _make_facade("tests/data/16319", tmp_path)
        output = tmp_path / "segment.sol.mmcif"
        
        result = export_segment_mmcif(facade, "SOL", output, results)
        
        assert result.exists()
        content = result.read_text()
        assert "SOL" in content or "ATOM" in content

    def test_records_segment_data(self, tmp_path: Path):
        facade, results = _make_facade("tests/data/14976_a", tmp_path)
        output = tmp_path / "popc.mmcif"
        export_segment_mmcif(facade, "seg_0_POPC", output, results)
        
        assert "popc.mmcif" in results.get_data("exports/segment_mmcif/seg_0_POPC")
