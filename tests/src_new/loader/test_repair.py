from __future__ import annotations

import pytest
import numpy as np

mdanalysis = pytest.importorskip("MDAnalysis")

from src_new.loader.repair import TopologyRepair, RepairReport
from src_new.loader.repair_constants import ATOMTABLE_ELEMENTS_MASSES
from src_new.config.loader import RunConfig


def _make_minimal_universe(n_atoms=4, with_elements=False):
    """Create a minimal in-memory universe with positions and basic topology.
    
    Args:
        n_atoms: Number of atoms
        with_elements: If True, include elements (which will auto-assign masses)
    """
    from MDAnalysis import Universe
    from MDAnalysis.core.topology import Topology
    from MDAnalysis.core.topologyattrs import Atomnames, Atomtypes, Resids, Resnames, Segids, Elements
    from MDAnalysis.coordinates.memory import MemoryReader
    
    # Create topology: n_atoms, 1 residue, 1 segment
    top = Topology(n_atoms, 1, 1)
    
    # Add minimal attrs
    top.add_TopologyAttr(Atomnames([f"AT{i}" for i in range(n_atoms)]))
    top.add_TopologyAttr(Atomtypes(["C", "H", "O", "N"][:n_atoms]))
    top.add_TopologyAttr(Resids([1]))  # one resid for one residue
    top.add_TopologyAttr(Resnames(["RES"]))  # one resname for one residue
    top.add_TopologyAttr(Segids(["SYSTEM"]))
    
    if with_elements:
        top.add_TopologyAttr(Elements(["C", "H", "O", "N"][:n_atoms]))
    
    # Create universe from topology
    u = Universe(top)
    
    # Add positions via MemoryReader
    positions = np.array([[0, 0, 0], [1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]], dtype=np.float32)[:n_atoms]
    u.load_new(positions, format='memory')
    
    return u


class TestGuessElements:
    def test_guesses_elements_from_types(self):
        u = _make_minimal_universe(4)
        # No elements initially
        config = RunConfig()
        config.loader.guess_missing_elements = True
        
        repair = TopologyRepair(u, config)
        count = repair.guess_elements()
        
        assert count == 4
        assert all(e for e in u.atoms.elements)

    def test_custom_fallback_from_names(self):
        u = _make_minimal_universe(4)
        # Clear types, set names with element prefixes
        u.atoms.types = ["", "", "", ""]
        u.atoms.names = ["CA", "H1", "O1", "N"]  # Use O1 instead of OG to avoid Og match
        
        config = RunConfig()
        config.loader.guess_missing_elements = True
        
        repair = TopologyRepair(u, config)
        repair._guess_elements_fallback()
        
        # Note: Single-letter prefix takes precedence over two-letter
        # "CA" -> "C" (Carbon), not "Ca" (Calcium)
        assert u.atoms.elements[0] == "C"
        assert u.atoms.elements[1] == "H"
        assert u.atoms.elements[2] == "O"
        assert u.atoms.elements[3] == "N"


class TestGuessMasses:
    def test_masses_derived_from_elements(self):
        """Test that when elements exist, masses are correctly derived.
        
        Note: MDAnalysis 2.10 auto-derives masses from elements, so this test
        verifies the integration works correctly rather than testing explicit
        mass guessing.
        """
        u = _make_minimal_universe(4, with_elements=True)
        
        config = RunConfig()
        config.loader.guess_missing_masses = True
        
        repair = TopologyRepair(u, config)
        # Masses already exist (derived from elements), so count should be 0
        count = repair.guess_masses()
        
        # Since MDAnalysis auto-derives masses from elements, no explicit guessing needed
        # but masses should be correct
        assert u.atoms.masses[0] == pytest.approx(ATOMTABLE_ELEMENTS_MASSES["C"])
        assert u.atoms.masses[1] == pytest.approx(ATOMTABLE_ELEMENTS_MASSES["H"])
        assert u.atoms.masses[2] == pytest.approx(ATOMTABLE_ELEMENTS_MASSES["O"])
        assert u.atoms.masses[3] == pytest.approx(ATOMTABLE_ELEMENTS_MASSES["N"])

    def test_custom_fallback_guesses_masses_from_elements(self):
        """Test custom fallback for mass guessing."""
        u = _make_minimal_universe(4, with_elements=True)
        
        # Clear masses to 0
        u.atoms.masses = [0.0, 0.0, 0.0, 0.0]
        
        repair = TopologyRepair(u, RunConfig())
        repair._guess_masses_fallback()
        
        assert u.atoms.masses[0] == pytest.approx(ATOMTABLE_ELEMENTS_MASSES["C"])
        assert u.atoms.masses[1] == pytest.approx(ATOMTABLE_ELEMENTS_MASSES["H"])


class TestFixNames:
    def test_fixes_duplicate_names_in_residue(self):
        u = _make_minimal_universe(4)
        u.atoms.names = ["CA", "CA", "CA", "CA"]
        
        config = RunConfig()
        config.loader.guess_missing_names = True
        
        repair = TopologyRepair(u, config)
        count = repair.fix_names()
        
        assert count == 3  # 3 duplicates fixed
        assert len(set(u.atoms.names)) == 4


class TestGuessBonds:
    def test_guesses_bonds_from_positions(self):
        u = _make_minimal_universe(4, with_elements=True)
        
        config = RunConfig()
        config.loader.guess_missing_bonds = True
        config.loader.bond_guess_vdw_factor = 0.55
        
        repair = TopologyRepair(u, config)
        count = repair.guess_bonds()
        
        assert count > 0
        assert hasattr(u.atoms, 'bonds')


class TestRepairReport:
    def test_report_to_dict_is_json_serializable(self):
        report = RepairReport(elements_guessed=2, masses_guessed=4, warnings=["missing_elements"])
        d = report.to_dict()
        import json
        json.dumps(d)


class TestInvalidElementStrings:
    """Tests for handling invalid/non-chemical element strings like GROMACS atom types."""
    
    def test_repair_guesses_invalid_elements_from_gromacs_types(self):
        """Test that invalid element strings (OW, HW1, MW) are re-guessed correctly.
        
        This is a regression test for issue where GROMACS TPR+GRO files had water
        atoms with element strings like 'OW', 'HW1', 'MW' instead of chemical symbols.
        TopologyRepair should detect these as invalid and re-guess them.
        """
        from MDAnalysis import Universe
        import numpy as np
        
        # Create minimal universe with 5 atoms
        n_atoms = 5
        u = Universe.empty(n_atoms, 1, atom_resindex=[0]*n_atoms, trajectory=True)
        u.add_TopologyAttr('names', ['O1', 'OW', 'HW1', 'MW', 'CA'])
        # Mix of valid ('O', 'C') and invalid ('OW', 'HW1', 'MW') element strings
        u.add_TopologyAttr('elements', ['O', 'OW', 'HW1', 'MW', 'C'])
        
        config = RunConfig()
        config.loader.guess_missing_elements = True
        
        repair = TopologyRepair(u, config)
        
        # _has_elements should return False because OW, HW1, MW are not valid
        assert not repair._has_elements(), "_has_elements should return False for invalid element strings"
        
        # Run guess_elements
        count = repair.guess_elements()
        
        # Get final elements
        final_elements = list(u.atoms.elements)
        
        # All elements should now be valid chemical symbols
        for elem in final_elements:
            assert elem.strip().capitalize() in ATOMTABLE_ELEMENTS_MASSES, f"Invalid element remains: {elem}"
        
        # Expected: O stays O, OW->O, HW1->H, MW->O, C stays C
        expected = ['O', 'O', 'H', 'O', 'C']
        assert final_elements == expected, f"Expected {expected}, got {final_elements}"
        
        # At least 3 should have been guessed (OW, HW1, MW)
        assert repair.report.elements_guessed >= 3, f"Expected >= 3 guessed, got {repair.report.elements_guessed}"
    
    def test_has_elements_with_mixed_valid_invalid(self):
        """Test _has_elements returns False when any element is invalid."""
        from MDAnalysis import Universe
        
        n_atoms = 3
        u = Universe.empty(n_atoms, 1, atom_resindex=[0]*n_atoms, trajectory=True)
        
        # Test case 1: all valid
        u.add_TopologyAttr('elements', ['C', 'H', 'O'])
        repair = TopologyRepair(u, RunConfig())
        assert repair._has_elements()
        
        # Test case 2: one invalid
        u.atoms.elements = ['C', 'OW', 'O']
        assert not repair._has_elements()
        
        # Test case 3: empty string counts as invalid
        u.atoms.elements = ['C', '', 'O']
        assert not repair._has_elements()
        
        # Test case 4: all invalid
        u.atoms.elements = ['OW', 'HW1', 'MW']
        assert not repair._has_elements()
    
    def test_is_valid_element_helper(self):
        """Test the _is_valid_element helper method."""
        from MDAnalysis import Universe
        
        repair = TopologyRepair(Universe.empty(1, 1), RunConfig())
        
        # Valid elements
        assert repair._is_valid_element('H')
        assert repair._is_valid_element('C')
        assert repair._is_valid_element('O')
        assert repair._is_valid_element('Na')
        assert repair._is_valid_element('Cl')
        
        # Case insensitivity
        assert repair._is_valid_element('h')
        assert repair._is_valid_element('c')
        assert repair._is_valid_element('o')
        assert repair._is_valid_element('NA')
        
        # Invalid elements (GROMACS atom types)
        assert not repair._is_valid_element('OW')
        assert not repair._is_valid_element('HW1')
        assert not repair._is_valid_element('MW')
        assert not repair._is_valid_element('CW')
        
        # Empty/whitespace
        assert not repair._is_valid_element('')
        assert not repair._is_valid_element(' ')
        assert not repair._is_valid_element(None)







class TestHasSufficientBonds:
    """Tests for _has_sufficient_bonds method."""
    
    def test_no_bonds_returns_false(self):
        """Test that _has_sufficient_bonds returns False when no bonds exist."""
        u = _make_minimal_universe(4)
        # No bonds in this universe
        
        repair = TopologyRepair(u, RunConfig())
        assert not repair._has_sufficient_bonds()
    
    def test_sufficient_bonds_returns_true(self):
        """Test that _has_sufficient_bonds returns True when bonds exist."""
        u = _make_minimal_universe(4, with_elements=True)
        
        config = RunConfig()
        config.loader.guess_missing_bonds = True
        config.loader.bond_guess_vdw_factor = 0.55
        
        repair = TopologyRepair(u, config)
        repair.guess_bonds()
        
        assert repair._has_sufficient_bonds()


class TestDeduplicateSegids:
    """Tests for _deduplicate_segids method."""
    
    def _make_two_segment_universe(self, segids):
        """Helper to create a universe with 2 segments and proper atom-segment mapping."""
        from MDAnalysis import Universe
        import numpy as np
        
        # Create empty universe with 6 atoms, 2 residues, 2 segments
        u = Universe.empty(6, n_residues=2, n_segments=2,
                           atom_resindex=[0, 0, 0, 1, 1, 1],  # atoms 0-2 in residue 0, atoms 3-5 in residue 1
                           residue_segindex=[0, 1],  # residue 0 in segment 0, residue 1 in segment 1
                           trajectory=True)
        u.add_TopologyAttr('names', ['N', 'CA', 'C', 'OW', 'HW1', 'HW2'])
        u.add_TopologyAttr('resids', [1, 2])
        u.add_TopologyAttr('resnames', ['ALA', 'HOH'])
        u.add_TopologyAttr('segids', segids)  # One segid per segment
        
        positions = np.array([[i, 0, 0] for i in range(6)], dtype=np.float32)
        u.load_new(positions, format='memory')
        return u
    
    def test_deduplicate_segids_renames_duplicates(self):
        """Test that duplicate segids are renamed to unique values."""
        from src_new.config.loader import RunConfig
        
        # Create universe with 2 segments sharing segid 'A'
        u = self._make_two_segment_universe(['A', 'A'])
        
        repair = TopologyRepair(u, RunConfig())
        repair._deduplicate_segids()
        
        segids = list(u.atoms.segids)
        # First 3 atoms should be one unique segid, last 3 another
        assert segids[0] != segids[3], f"Expected different segids, got {segids[0]} == {segids[3]}"
        assert set(segids[:3]) == set([segids[0]]), f"Expected first 3 atoms to have same segid"
        assert set(segids[3:]) == set([segids[3]]), f"Expected last 3 atoms to have same segid"
    
    def test_deduplicate_segids_no_duplicates(self):
        """Test that segids are unchanged when there are no duplicates."""
        from src_new.config.loader import RunConfig
        
        # Create universe with 2 segments with unique segids
        u = self._make_two_segment_universe(['A', 'B'])
        
        repair = TopologyRepair(u, RunConfig())
        repair._deduplicate_segids()
        
        segids = list(u.atoms.segids)
        # Should remain unchanged
        assert set(segids[:3]) == {"A"}
        assert set(segids[3:]) == {"B"}
    
    def test_deduplicate_segids_in_run(self):
        """Test that _deduplicate_segids is called during run()."""
        from src_new.config.loader import RunConfig
        
        # Create universe with 2 segments sharing segid 'A'
        u = self._make_two_segment_universe(['A', 'A'])
        
        config = RunConfig()
        repair = TopologyRepair(u, config)
        repair.run()
        
        segids = list(u.atoms.segids)
        # Should have been deduplicated
        assert segids[0] != segids[3], f"Expected different segids after run(), got {segids[0]} == {segids[3]}"
