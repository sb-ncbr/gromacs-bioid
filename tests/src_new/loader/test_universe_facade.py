from __future__ import annotations

import pytest

mdanalysis = pytest.importorskip("MDAnalysis")

from pathlib import Path
from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import load_simulation
from src_new.loader.repair import TopologyRepair
from src_new.loader.universe_facade import (
    LoadedUniverse,
    SegmentProperty,
    UniverseParameter,
)
from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager


def _load_and_facade(data_dir: str, tmp_path: Path, filter_segments=None):
    """Helper: inspect, load, repair, create facade."""
    root = Path(data_dir)
    bundle = inspect_directory(root)
    decision = select_best_file_combination(bundle)
    
    results_path = tmp_path / "results.json"
    results = ResultsManager(results_path)
    
    config = RunConfig()
    config.loader.guess_missing_elements = True
    config.loader.guess_missing_masses = True
    config.loader.guess_missing_bonds = True  # needed for fragments on PDB/GRO-only
    
    load_result = load_simulation(decision, bundle, config, results)
    if not load_result.success:
        pytest.skip(f"Could not load data from {data_dir}: {load_result.attempts[0].error_message if load_result.attempts else 'unknown'}")
    
    repair = TopologyRepair(load_result.universe, config)
    repair_report = repair.run()
    
    facade = LoadedUniverse(
        universe=load_result.universe,
        decision=decision,
        repair_report=repair_report,
        results=results,
        filter_segments=filter_segments,
    )
    return facade, results


class TestFacade14976a:
    """Test with TPR-only GROMACS data."""
    
    def test_counts(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/14976_a", tmp_path)
        
        assert facade.get_parameter(UniverseParameter.ATOM_COUNT) == 82308
        assert facade.get_parameter(UniverseParameter.RESIDUE_COUNT) == 14896
        assert facade.get_parameter(UniverseParameter.SEGMENT_COUNT) == 4
        assert facade.get_parameter(UniverseParameter.FRAGMENT_COUNT) == 14896
    
    def test_segments(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/14976_a", tmp_path)
        
        assert facade.get_segments() == {'seg_0_POPC', 'seg_2_NA', 'seg_1_SOL', 'seg_3_CL'}
    
    def test_segment_flags(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/14976_a", tmp_path)
        
        popc = facade.get_segment_properties("seg_0_POPC")
        assert popc.flags[SegmentProperty.HAS_ELEMENTS.value] is False
        assert popc.flags[SegmentProperty.HAS_MASSES.value] is True
        assert popc.flags[SegmentProperty.HAS_POSITIONS.value] is True  # positions in TPR
        assert popc.flags[SegmentProperty.HAS_NAMES.value] is True
        
        na = facade.get_segment_properties("seg_2_NA")
        assert na.flags[SegmentProperty.HAS_ELEMENTS.value] is True
        assert na.flags[SegmentProperty.HAS_MASSES.value] is True
        assert na.flags[SegmentProperty.HAS_NAMES.value] is True
    
    def test_fragment_counts(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/14976_a", tmp_path)
        
        for segment in facade.get_segments():
            props = facade.get_segment_properties(segment)
            fragment = facade.get_fragment(segment)
            selected = facade.universe.select_atoms(f"segid {segment}")
            
            assert props.atom_count_fragment == len(fragment.atoms)
            assert props.bond_count_fragment == len(fragment.bonds)
            assert props.atom_count_total == len(selected.atoms)
            assert props.bond_count_total == len(selected.bonds)
            assert props.molecule_count == len(selected.fragments)
            assert props.molecule_count >= 1
    
    def test_fragment_popc(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/14976_a", tmp_path)
        
        popc = facade.get_fragment("seg_0_POPC")
        assert len(popc.atoms) > 1
        
        na = facade.get_fragment("seg_2_NA")
        assert len(na.atoms) == 1
        
        sol = facade.get_fragment("seg_1_SOL")
        assert set(sol.residues.resnames) == {"SOL"}
    
    def test_results_recorded(self, tmp_path: Path):
        facade, results = _load_and_facade("tests/data/14976_a", tmp_path)
        
        assert results.data_exists("universe/segments/seg_0_POPC/properties")
        assert results.get_data("universe/parameters/atom_count") == 82308
        assert results.get_data("universe/segment_list") == sorted(facade.get_segments())


class TestFacade16319:
    """Test with TOP+GRO GROMACS data."""
    
    def test_counts(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/16319", tmp_path)
        
        assert facade.get_parameter(UniverseParameter.ATOM_COUNT) == 12208
        assert facade.get_parameter(UniverseParameter.RESIDUE_COUNT) == 2952
        assert facade.get_parameter(UniverseParameter.SEGMENT_COUNT) == 2952
        assert facade.get_parameter(UniverseParameter.FRAGMENT_COUNT) == 2952
    
    def test_segments(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/16319", tmp_path)
        
        assert facade.get_segments() == {'DPPC', 'SOL', 'Na', 'Cl'}
    
    def test_segment_properties(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/16319", tmp_path)
        
        for segment in facade.get_segments():
            props = facade.get_segment_properties(segment)
            assert props.flags[SegmentProperty.HAS_ELEMENTS.value] is True
            assert props.flags[SegmentProperty.HAS_MASSES.value] is True
            assert props.flags[SegmentProperty.HAS_POSITIONS.value] is True
            assert props.flags[SegmentProperty.HAS_NAMES.value] is True
    
    def test_fragment(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/16319", tmp_path)
        
        assert len(facade.get_fragment("Na").atoms) == 1
        assert len(facade.get_fragment("Cl").atoms) == 1
        assert set(facade.get_fragment("SOL").residues.resnames) == {"SOL"}
        assert set(facade.get_fragment("DPPC").residues.resnames) == {"DPPC"}


class TestFacade35193a:
    def test_counts(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/35193_a", tmp_path)
        
        assert facade.get_parameter(UniverseParameter.ATOM_COUNT) == 53962
        assert facade.get_parameter(UniverseParameter.RESIDUE_COUNT) == 9362
        assert facade.get_parameter(UniverseParameter.SEGMENT_COUNT) == 4
        assert facade.get_parameter(UniverseParameter.FRAGMENT_COUNT) == 9362
    
    def test_segments(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/35193_a", tmp_path)
        
        assert facade.get_segments() == {'seg_2_Na_s', 'seg_1_TIP3p', 'seg_0_POPC', 'seg_3_Cl_s'}
    
    def test_flags(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/35193_a", tmp_path)
        
        for segment in facade.get_segments():
            props = facade.get_segment_properties(segment)
            assert props.flags[SegmentProperty.HAS_ELEMENTS.value] is True
            assert props.flags[SegmentProperty.HAS_MASSES.value] is True
            assert props.flags[SegmentProperty.HAS_POSITIONS.value] is True
            assert props.flags[SegmentProperty.HAS_NAMES.value] is True


class TestFacade1010142:
    """Test with TOP+GRO protein data - skipped if force field files missing."""
    
    def test_counts(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/1010142", tmp_path)
        
        assert facade.get_parameter(UniverseParameter.ATOM_COUNT) == 27755
        assert facade.get_parameter(UniverseParameter.RESIDUE_COUNT) == 8860
        assert facade.get_parameter(UniverseParameter.SEGMENT_COUNT) == 8769
        assert facade.get_parameter(UniverseParameter.FRAGMENT_COUNT) == 8769
    
    def test_segments(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/1010142", tmp_path)
        
        assert facade.get_segments() == {'SOL', 'Protein'}
    
    def test_protein_flags(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/1010142", tmp_path)
        
        protein = facade.get_segment_properties("Protein")
        assert protein.flags[SegmentProperty.IS_PROTEIN.value] is True
        assert protein.flags[SegmentProperty.HAS_ELEMENTS.value] is True


class TestMoleculeExtraction:
    def test_extract_molecule_instances(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/14976_a", tmp_path)
        
        instances = facade.extract_all_molecule_instances()
        assert len(instances) == 4
        
        # Find Na instance
        na_instance = next(i for i in instances if i.segment_ids == ['seg_2_NA'])
        assert na_instance.atom_count == 1
        assert na_instance.molecule_type.value == "ion"
    
    def test_molecule_instance_has_composition(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/16319", tmp_path)
        
        sol = facade.extract_molecule_instance("SOL")
        assert sol.atom_count == 3
        assert sol.molecule_type.value == "water"
        assert "O" in sol.element_composition
        assert "H" in sol.element_composition


class TestFilterSegments:
    def test_filter_excludes_segments(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/14976_a", tmp_path, filter_segments={"seg_0_POPC"})
        
        assert facade.get_segments() == {"seg_0_POPC"}
        assert "seg_1_SOL" not in facade.get_segments()
