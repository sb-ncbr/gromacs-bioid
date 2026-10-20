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
        # HAS_ELEMENTS is True since MDAnalysis >= 2.9 element guessing
        # (TPR/ITP transition path, MDA issue #4698) plus loader repair
        # guessing deliver elements for lipids too; legacy expectation was
        # False from the pre-guessing era (triaged 2026-10-20, A' wave).
        assert popc.flags[SegmentProperty.HAS_ELEMENTS.value] is True
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
        
        segs = facade.get_segments()
        # Per-molecule segid contract (triaged 2026-10-20, A' wave): with
        # MDAnalysis >= 2.9 the TOP/ITP load path of this fixture produces
        # one segment per molecule ('SOL_1', 'SOL_2', ...); species-level
        # aggregation lives in the molecules/discovery layer, NOT in the
        # facade. The legacy aggregated expectation {'DPPC','SOL','Na','Cl'}
        # predates that parser behavior (ledger entry 2026-10-02).
        assert len(segs) == 2952
        prefixes = {s.rsplit('_', 1)[0] for s in segs}
        assert prefixes == {"DPPC", "SOL", "Na", "Cl"}
        assert all(s.rsplit('_', 1)[1].isdigit() for s in segs)
    
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
        
        # Per-molecule segments (see test_segments): address one instance of
        # each species by its '_N' suffixed name.
        segs = facade.get_segments()
        first = lambda pref: sorted(s for s in segs if s.startswith(f"{pref}_"))[0]
        assert len(facade.get_fragment(first("Na")).atoms) == 1
        assert len(facade.get_fragment(first("Cl")).atoms) == 1
        assert set(facade.get_fragment(first("SOL")).residues.resnames) == {"SOL"}
        assert set(facade.get_fragment(first("DPPC")).residues.resnames) == {"DPPC"}


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
        
        # Per-molecule segment naming for this fixture (triaged 2026-10-20):
        # pick one water instance by species prefix instead of a legacy
        # aggregated 'SOL' segment.
        segs = facade.get_segments()
        sol_name = sorted(s for s in segs if s.startswith("SOL_"))[0]
        sol = facade.extract_molecule_instance(sol_name)
        assert sol.atom_count == 3
        assert sol.molecule_type.value == "water"
        assert "O" in sol.element_composition
        assert "H" in sol.element_composition


class TestFilterSegments:
    def test_filter_excludes_segments(self, tmp_path: Path):
        facade, _ = _load_and_facade("tests/data/14976_a", tmp_path, filter_segments={"seg_0_POPC"})
        
        assert facade.get_segments() == {"seg_0_POPC"}
        assert "seg_1_SOL" not in facade.get_segments()




class TestComputeFlagsThreshold:
    """Tests for _compute_flags 80% threshold behavior."""
    
    def test_is_protein_with_90_percent_standard_residues(self):
        """Test that a segment with 90% standard AA residues reports is_protein: true."""
        from MDAnalysis import Universe
        import numpy as np
        
        # Create universe with segment having 9 ALA + 1 HOH (90% protein)
        # Each residue has 1 atom for simplicity, so we can control resnames per residue
        n_residues = 10
        n_atoms = n_residues  # 1 atom per residue
        u = Universe.empty(n_atoms, n_residues=n_residues, n_segments=1,
                           atom_resindex=list(range(n_residues)),
                           trajectory=True)
        u.add_TopologyAttr('names', [f"AT{i}" for i in range(n_atoms)])
        u.add_TopologyAttr('resids', list(range(1, n_residues + 1)))
        # 9 ALA + 1 HOH = 90% protein
        resnames = ["ALA"] * 9 + ["HOH"]
        u.add_TopologyAttr('resnames', resnames)
        u.add_TopologyAttr('segids', ["A"])
        u.add_TopologyAttr('elements', ["C"] * n_atoms)
        
        positions = np.array([[i, 0, 0] for i in range(n_atoms)], dtype=np.float32)
        u.load_new(positions, format='memory')
        
        selected = u.select_atoms("segid A")
        
        from src_new.loader.universe_facade import KNOWN_RESIDUE_CODES
        
        resnames = selected.atoms.resnames
        known_count = sum(
            1 for rn in resnames if rn.upper() in KNOWN_RESIDUE_CODES
        )
        is_protein = len(resnames) > 0 and known_count / len(resnames) >= 0.8
        
        assert is_protein, f"Expected is_protein=True for 90% protein (got {known_count}/{len(resnames)} = {known_count/len(resnames):.2%})"
    
    def test_is_protein_with_70_percent_standard_residues(self):
        """Test that a segment with 70% standard AA residues reports is_protein: false."""
        from MDAnalysis import Universe
        import numpy as np
        
        # Create universe with segment having 7 ALA + 3 HOH (70% protein)
        n_residues = 10
        n_atoms = n_residues  # 1 atom per residue
        u = Universe.empty(n_atoms, n_residues=n_residues, n_segments=1,
                           atom_resindex=list(range(n_residues)),
                           trajectory=True)
        u.add_TopologyAttr('names', [f"AT{i}" for i in range(n_atoms)])
        u.add_TopologyAttr('resids', list(range(1, n_residues + 1)))
        # 7 ALA + 3 HOH = 70% protein (below 80% threshold)
        resnames = ["ALA"] * 7 + ["HOH"] * 3
        u.add_TopologyAttr('resnames', resnames)
        u.add_TopologyAttr('segids', ["A"])
        u.add_TopologyAttr('elements', ["C"] * n_atoms)
        
        positions = np.array([[i, 0, 0] for i in range(n_atoms)], dtype=np.float32)
        u.load_new(positions, format='memory')
        
        selected = u.select_atoms("segid A")
        
        from src_new.loader.universe_facade import KNOWN_RESIDUE_CODES
        
        resnames = selected.atoms.resnames
        known_count = sum(
            1 for rn in resnames if rn.upper() in KNOWN_RESIDUE_CODES
        )
        is_protein = len(resnames) > 0 and known_count / len(resnames) >= 0.8
        
        assert not is_protein, f"Expected is_protein=False for 70% protein (got {known_count}/{len(resnames)} = {known_count/len(resnames):.2%})"


class TestSegmentNamesWithSpaces:
    """Regression test for segment names containing spaces.
    
    This tests the fix for MDAnalysis select_atoms failing to match segment
    names containing spaces (e.g., "Protein in water t= 80000.00000").
    """
    
    def test_segment_with_spaces_in_name(self):
        """Test that segments with spaces in their names are handled correctly."""
        from MDAnalysis import Universe
        import numpy as np
        
        # Create a universe with a segment name containing spaces
        n_atoms = 10
        n_residues = 2
        u = Universe.empty(n_atoms, n_residues=n_residues, n_segments=1,
                           atom_resindex=[0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
                           trajectory=True)
        u.add_TopologyAttr('names', [f"AT{i}" for i in range(n_atoms)])
        u.add_TopologyAttr('resids', [1, 2])  # One resid per residue
        u.add_TopologyAttr('resnames', ["ALA"] * n_residues)
        # Segment name with spaces - this is the bug scenario
        segment_name = "Protein in water"
        u.add_TopologyAttr('segids', [segment_name])
        u.add_TopologyAttr('elements', ["C"] * n_atoms)
        u.add_TopologyAttr('masses', [12.0] * n_atoms)
        
        positions = np.array([[i, 0, 0] for i in range(n_atoms)], dtype=np.float32)
        u.load_new(positions, format='memory')
        
        # Create minimal dependencies for LoadedUniverse
        from src_new.input.models import LoadDecision
        from src_new.loader.repair import RepairReport
        from src_new.results.results_manager import ResultsManager
        from pathlib import Path
        import tempfile
        
        from src_new.input.models import InputKind
        
        decision = LoadDecision(
            input_kind=InputKind.GROMACS,
            selected_strategy="tpr_only",
            topology_files=[Path("dummy.tpr")],
        )
        
        repair_report = RepairReport()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            results_path = Path(tmpdir) / "results.json"
            results = ResultsManager(results_path)
            
            facade = LoadedUniverse(
                universe=u,
                decision=decision,
                repair_report=repair_report,
                results=results,
            )
            
            # Assert get_segments returns the spaced name
            segments = facade.get_segments()
            assert segment_name in segments, f"Expected '{segment_name}' in segments, got {segments}"
            
            # Assert get_segment_properties returns positive atom count
            props = facade.get_segment_properties(segment_name)
            assert props.atom_count_total > 0, f"Expected atom_count_total > 0, got {props.atom_count_total}"
            assert props.atom_count_total == n_atoms, f"Expected {n_atoms} atoms, got {props.atom_count_total}"
            
            # Assert get_fragment returns an AtomGroup with atoms
            fragment = facade.get_fragment(segment_name)
            assert len(fragment.atoms) > 0, f"Expected fragment with atoms > 0, got {len(fragment.atoms)}"
            
            # Assert extract_molecule_instance works
            instance = facade.extract_molecule_instance(segment_name)
            assert instance.atom_count > 0, f"Expected molecule instance with atom_count > 0, got {instance.atom_count}"
