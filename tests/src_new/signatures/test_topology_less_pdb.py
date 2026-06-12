"""Unit tests for topology-less PDB generators."""

from __future__ import annotations

import pytest

mdanalysis = pytest.importorskip("MDAnalysis")

import numpy as np
from MDAnalysis import Universe
from MDAnalysis.core.topologyattrs import Resnums
from unittest.mock import MagicMock

from src_new.signatures.generators.topology_less_pdb import (
    TopologyLessPDBGenerator,
    CAOnlyPDBGenerator,
    fragment_to_pdb_topology_less,
    fragment_to_pdb_ca_only,
)
from src_new.signatures.registry import get_default_generators
from src_new.config.loader import SignaturesConfig
from src_new.loader.universe_facade import SegmentProperty


def _create_protein_universe(n_atoms=5):
    """Create a minimal protein universe for testing.
    
    Creates a universe with n_atoms atoms across 3 residues (ALA, ALA, GLY).
    Has positions but NO bonds.
    """
    n_residues = 3
    u = Universe.empty(
        n_atoms, 
        n_residues=n_residues, 
        n_segments=1,
        atom_resindex=[0, 0, 1, 1, 2][:n_atoms],
        trajectory=True
    )
    
    # Add topology attributes (per-atom or per-residue as appropriate)
    atom_names = ['N', 'CA', 'C', 'O', 'CB'][:n_atoms]
    resnames = ['ALA', 'ALA', 'GLY'][:min(n_residues, 3)]
    resnums = [1, 1, 2][:min(n_residues, 3)]  # Per-residue values
    
    u.add_TopologyAttr('names', atom_names)
    u.add_TopologyAttr('resnames', resnames)
    u.add_TopologyAttr(Resnums(resnums))  # Use Resnums class for per-residue
    u.add_TopologyAttr('segids', ['A'])
    u.add_TopologyAttr('elements', ['N', 'C', 'C', 'O', 'C'][:n_atoms])
    
    # Add positions
    positions = np.zeros((n_atoms, 3), dtype=np.float32)
    u.load_new(positions, format='memory')
    
    return u


def _create_ca_only_universe():
    """Create a universe with some CA atoms and some non-CA atoms."""
    # 6 atoms: N, CA, C, O from residue 1, then N, CA from residue 2
    n_atoms = 6
    n_residues = 2
    
    u = Universe.empty(
        n_atoms, 
        n_residues=n_residues, 
        n_segments=1,
        atom_resindex=[0, 0, 0, 0, 1, 1],
        trajectory=True
    )
    
    u.add_TopologyAttr('names', ['N', 'CA', 'C', 'O', 'N', 'CA'])
    u.add_TopologyAttr('resnames', ['ALA', 'ALA'])
    u.add_TopologyAttr(Resnums([1, 2]))  # Per-residue
    u.add_TopologyAttr('segids', ['A'])
    u.add_TopologyAttr('elements', ['N', 'C', 'C', 'O', 'N', 'C'])
    
    positions = np.zeros((n_atoms, 3), dtype=np.float32)
    u.load_new(positions, format='memory')
    
    return u


def _create_no_ca_universe():
    """Create a universe with no CA atoms."""
    n_atoms = 4
    n_residues = 1
    
    u = Universe.empty(
        n_atoms, 
        n_residues=n_residues, 
        n_segments=1,
        atom_resindex=[0, 0, 0, 0],
        trajectory=True
    )
    
    u.add_TopologyAttr('names', ['N', 'C', 'O', 'CB'])
    u.add_TopologyAttr('resnames', ['ALA'])
    u.add_TopologyAttr(Resnums([1]))  # Per-residue
    u.add_TopologyAttr('segids', ['A'])
    u.add_TopologyAttr('elements', ['N', 'C', 'O', 'C'])
    
    positions = np.zeros((n_atoms, 3), dtype=np.float32)
    u.load_new(positions, format='memory')
    
    return u


def _create_mock_facade(is_protein=True, has_positions=True):
    """Create a mock LoadedUniverse facade for testing."""
    facade = MagicMock()
    
    props = MagicMock()
    props.flags = {
        SegmentProperty.IS_PROTEIN.value: is_protein,
        SegmentProperty.IS_NUCLEIC.value: False,
        SegmentProperty.HAS_POSITIONS.value: has_positions,
        SegmentProperty.HAS_ELEMENTS.value: True,
        SegmentProperty.HAS_NAMES.value: True,
    }
    
    facade.get_segment_properties.return_value = props
    return facade


def _create_mock_instance():
    """Create a minimal mock MoleculeInstance."""
    instance = MagicMock()
    return instance


class TestTopologyLessPDBGenerator:
    """Tests for TopologyLessPDBGenerator."""
    
    def test_is_applicable_protein(self):
        """Test is_applicable returns True for protein segment."""
        config = SignaturesConfig()
        config.topology_less_pdb = True
        gen = TopologyLessPDBGenerator(config)
        
        u = _create_protein_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == True
    
    def test_is_applicable_nucleic(self):
        """Test is_applicable returns True for nucleic segment."""
        config = SignaturesConfig()
        config.topology_less_pdb = True
        gen = TopologyLessPDBGenerator(config)
        
        u = _create_protein_universe()
        fragment = u.select_atoms("segid A")
        
        facade = _create_mock_facade(is_protein=False, has_positions=True)
        facade.get_segment_properties.return_value.flags[SegmentProperty.IS_NUCLEIC.value] = True
        
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == True
    
    def test_is_applicable_no_positions(self):
        """Test is_applicable returns False when no positions."""
        config = SignaturesConfig()
        config.topology_less_pdb = True
        gen = TopologyLessPDBGenerator(config)
        
        u = _create_protein_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=False)
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == False
    
    def test_is_applicable_not_protein_or_nucleic(self):
        """Test is_applicable returns False for non-protein/nucleic."""
        config = SignaturesConfig()
        config.topology_less_pdb = True
        gen = TopologyLessPDBGenerator(config)
        
        u = _create_protein_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=False, has_positions=True)
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == False
    
    def test_is_applicable_disabled(self):
        """Test is_applicable returns False when generator disabled."""
        config = SignaturesConfig()
        config.topology_less_pdb = False
        gen = TopologyLessPDBGenerator(config)
        
        u = _create_protein_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == False
    
    def test_generate_returns_valid_pdb(self):
        """Test generate returns a valid PDB string with ATOM lines."""
        config = SignaturesConfig()
        config.topology_less_pdb = True
        gen = TopologyLessPDBGenerator(config)
        
        u = _create_protein_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        pdb_str = gen.generate(instance, fragment, facade)
        
        assert pdb_str is not None
        assert "ATOM" in pdb_str
        assert "ALA" in pdb_str
        assert "GLY" in pdb_str
    
    def test_generate_no_conect_records(self):
        """Test generate does NOT produce CONECT records."""
        config = SignaturesConfig()
        config.topology_less_pdb = True
        gen = TopologyLessPDBGenerator(config)
        
        u = _create_protein_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        pdb_str = gen.generate(instance, fragment, facade)
        
        assert "CONECT" not in pdb_str
    
    def test_generate_has_end_record(self):
        """Test generate includes END record."""
        config = SignaturesConfig()
        config.topology_less_pdb = True
        gen = TopologyLessPDBGenerator(config)
        
        u = _create_protein_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        pdb_str = gen.generate(instance, fragment, facade)
        
        assert "END" in pdb_str
    
    def test_generate_atom_count(self):
        """Test generate produces correct number of ATOM lines."""
        config = SignaturesConfig()
        config.topology_less_pdb = True
        gen = TopologyLessPDBGenerator(config)
        
        u = _create_protein_universe(n_atoms=5)
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        pdb_str = gen.generate(instance, fragment, facade)
        
        atom_lines = [line for line in pdb_str.split('\n') if line.startswith('ATOM')]
        assert len(atom_lines) == 5


class TestCAOnlyPDBGenerator:
    """Tests for CAOnlyPDBGenerator."""
    
    def test_is_applicable_with_ca_atoms(self):
        """Test is_applicable returns True when CA atoms exist."""
        config = SignaturesConfig()
        config.ca_only_pdb = True
        gen = CAOnlyPDBGenerator(config)
        
        u = _create_ca_only_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == True
    
    def test_is_applicable_no_ca_atoms(self):
        """Test is_applicable returns False when no CA atoms exist."""
        config = SignaturesConfig()
        config.ca_only_pdb = True
        gen = CAOnlyPDBGenerator(config)
        
        u = _create_no_ca_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == False
    
    def test_is_applicable_not_protein(self):
        """Test is_applicable returns False for non-protein."""
        config = SignaturesConfig()
        config.ca_only_pdb = True
        gen = CAOnlyPDBGenerator(config)
        
        u = _create_ca_only_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=False, has_positions=True)
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == False
    
    def test_is_applicable_no_positions(self):
        """Test is_applicable returns False when no positions."""
        config = SignaturesConfig()
        config.ca_only_pdb = True
        gen = CAOnlyPDBGenerator(config)
        
        u = _create_ca_only_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=False)
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == False
    
    def test_is_applicable_disabled(self):
        """Test is_applicable returns False when generator disabled."""
        config = SignaturesConfig()
        config.ca_only_pdb = False
        gen = CAOnlyPDBGenerator(config)
        
        u = _create_ca_only_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        assert gen.is_applicable(instance, fragment, facade) == False
    
    def test_generate_returns_only_ca_atoms(self):
        """Test generate returns PDB with only CA atoms."""
        config = SignaturesConfig()
        config.ca_only_pdb = True
        gen = CAOnlyPDBGenerator(config)
        
        u = _create_ca_only_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        pdb_str = gen.generate(instance, fragment, facade)
        
        assert pdb_str is not None
        assert "ATOM" in pdb_str
        
        # Check that only CA atoms are in the output
        atom_lines = [line for line in pdb_str.split('\n') if line.startswith('ATOM')]
        for line in atom_lines:
            # Atom name is in columns 13-16 (0-indexed 12-16)
            atom_name = line[12:16].strip()
            assert atom_name == "CA"
    
    def test_generate_no_conect_records(self):
        """Test generate does NOT produce CONECT records."""
        config = SignaturesConfig()
        config.ca_only_pdb = True
        gen = CAOnlyPDBGenerator(config)
        
        u = _create_ca_only_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        pdb_str = gen.generate(instance, fragment, facade)
        
        assert "CONECT" not in pdb_str
    
    def test_generate_atom_count_matches_ca_count(self):
        """Test generate produces ATOM lines equal to number of CA atoms."""
        config = SignaturesConfig()
        config.ca_only_pdb = True
        gen = CAOnlyPDBGenerator(config)
        
        u = _create_ca_only_universe()
        fragment = u.select_atoms("segid A")
        facade = _create_mock_facade(is_protein=True, has_positions=True)
        instance = _create_mock_instance()
        
        # Count CA atoms in fragment
        ca_count = np.sum(fragment.atoms.names == "CA")
        
        pdb_str = gen.generate(instance, fragment, facade)
        atom_lines = [line for line in pdb_str.split('\n') if line.startswith('ATOM')]
        
        assert len(atom_lines) == ca_count


class TestFragmentToPDBFunctions:
    """Tests for the helper functions fragment_to_pdb_*"""
    
    def test_fragment_to_pdb_topology_less_basic(self):
        """Test fragment_to_pdb_topology_less produces valid PDB."""
        u = _create_protein_universe()
        fragment = u.select_atoms("segid A")
        
        pdb_str = fragment_to_pdb_topology_less(fragment)
        
        assert pdb_str is not None
        assert "HEADER" in pdb_str
        assert "END" in pdb_str
        assert "CONECT" not in pdb_str
    
    def test_fragment_to_pdb_ca_only_basic(self):
        """Test fragment_to_pdb_ca_only produces valid PDB with only CA."""
        u = _create_ca_only_universe()
        fragment = u.select_atoms("segid A")
        
        pdb_str = fragment_to_pdb_ca_only(fragment)
        
        assert pdb_str is not None
        assert "HEADER" in pdb_str
        assert "END" in pdb_str
        assert "CONECT" not in pdb_str
        
        # Verify only CA atoms
        atom_lines = [line for line in pdb_str.split('\n') if line.startswith('ATOM')]
        for line in atom_lines:
            atom_name = line[12:16].strip()
            assert atom_name == "CA"


class TestRegistryIntegration:
    """Tests for integration with the signature registry."""
    
    def test_default_generators_contains_topology_less_pdb(self):
        """Test that default generators includes topology_less_pdb."""
        config = SignaturesConfig()
        generators = get_default_generators(config)
        
        names = [gen.name for gen in generators]
        assert "topology_less_pdb" in names
    
    def test_default_generators_contains_ca_only_pdb(self):
        """Test that default generators includes ca_only_pdb."""
        config = SignaturesConfig()
        generators = get_default_generators(config)
        
        names = [gen.name for gen in generators]
        assert "ca_only_pdb" in names
    
    def test_generator_instances_have_correct_names(self):
        """Test that generator instances have correct name attributes."""
        config = SignaturesConfig()
        generators = get_default_generators(config)
        
        for gen in generators:
            if gen.name == "topology_less_pdb":
                assert isinstance(gen, TopologyLessPDBGenerator)
            elif gen.name == "ca_only_pdb":
                assert isinstance(gen, CAOnlyPDBGenerator)
