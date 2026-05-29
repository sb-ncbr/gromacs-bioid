"""Tests for molecule uniqueness determination."""

import pytest

from src_new.molecules.instances import MoleculeInstance, MoleculeType
from src_new.molecules.uniqueness import (
    compute_uniqueness_key,
    collapse_to_unique_instances,
    group_by_uniqueness,
    count_unique_by_type,
    create_fingerprint,
    MolecularFingerprint,
)


@pytest.fixture
def protein_instance():
    """Create a sample protein instance."""
    return MoleculeInstance(
        instance_id="mol_INST_000001",
        atom_indices=list(range(100)),
        residue_indices=list(range(10)),
        segment_ids=["A"],
        chain_ids=["A"],
        resids=list(range(1, 11)),
        resnames=["ALA", "GLY", "SER", "THR", "VAL", "LEU", "ILE", "ASP", "GLU", "LYS"],
        molecule_type=MoleculeType.PROTEIN,
        copy_number=1,
        confidence=0.9,
        provenance={"method": "test"},
        atom_count=100,
        element_composition={"C": 50, "H": 80, "N": 10, "O": 15, "S": 2},
    )


@pytest.fixture
def identical_protein_instance():
    """Create an identical protein (different instance)."""
    return MoleculeInstance(
        instance_id="mol_INST_000002",
        atom_indices=list(range(100, 200)),
        residue_indices=list(range(10, 20)),
        segment_ids=["B"],
        chain_ids=["B"],
        resids=list(range(1, 11)),  # Same residues
        resnames=["ALA", "GLY", "SER", "THR", "VAL", "LEU", "ILE", "ASP", "GLU", "LYS"],
        molecule_type=MoleculeType.PROTEIN,
        copy_number=2,
        confidence=0.9,
        provenance={"method": "test"},
        atom_count=100,
        element_composition={"C": 50, "H": 80, "N": 10, "O": 15, "S": 2},
    )


@pytest.fixture
def different_protein_instance():
    """Create a different protein sequence."""
    return MoleculeInstance(
        instance_id="mol_INST_000003",
        atom_indices=list(range(200, 300)),
        residue_indices=list(range(20, 30)),
        segment_ids=["C"],
        chain_ids=["C"],
        resids=list(range(1, 11)),
        resnames=["MET", "PRO", "PHE", "TRP", "HIS", "ARG", "ASN", "GLN", "CYS", "TYR"],
        molecule_type=MoleculeType.PROTEIN,
        copy_number=1,
        confidence=0.9,
        provenance={"method": "test"},
        atom_count=100,
        element_composition={"C": 60, "H": 90, "N": 15, "O": 12, "S": 4},
    )


@pytest.fixture
def water_instance():
    """Create a water molecule instance."""
    return MoleculeInstance(
        instance_id="mol_INST_000004",
        atom_indices=[0, 1, 2],
        residue_indices=[0],
        segment_ids=["W"],
        chain_ids=["W"],
        resids=[1],
        resnames=["HOH"],
        molecule_type=MoleculeType.WATER,
        copy_number=1,
        confidence=1.0,
        provenance={"method": "test"},
        atom_count=3,
    )


@pytest.fixture
def ion_instance():
    """Create an ion instance."""
    return MoleculeInstance(
        instance_id="mol_INST_000005",
        atom_indices=[0],
        residue_indices=[0],
        segment_ids=["I"],
        chain_ids=["I"],
        resids=[1],
        resnames=["NA"],
        molecule_type=MoleculeType.ION,
        copy_number=1,
        confidence=1.0,
        provenance={"method": "test"},
        atom_count=1,
        element_composition={"NA": 1},
    )


class TestComputeUniquenessKey:
    """Tests for uniqueness key computation."""

    def test_same_sequence_same_key(self, protein_instance, identical_protein_instance):
        """Identical sequences produce same key."""
        key1 = compute_uniqueness_key(protein_instance)
        key2 = compute_uniqueness_key(identical_protein_instance)
        assert key1 == key2

    def test_different_sequence_different_key(self, protein_instance, different_protein_instance):
        """Different sequences produce different keys."""
        key1 = compute_uniqueness_key(protein_instance)
        key2 = compute_uniqueness_key(different_protein_instance)
        assert key1 != key2

    def test_key_includes_molecule_type(self, protein_instance, water_instance):
        """Keys include molecule type."""
        key1 = compute_uniqueness_key(protein_instance)
        key2 = compute_uniqueness_key(water_instance)
        assert "protein" in key1
        assert "water" in key2

    def test_key_format(self, protein_instance):
        """Key has expected format."""
        key = compute_uniqueness_key(protein_instance)
        assert "protein" in key
        assert "atoms:" in key
        assert "residues:" in key


class TestCollapseToUniqueInstances:
    """Tests for collapsing to unique instances."""

    def test_collapses_duplicates(self, protein_instance, identical_protein_instance):
        """Duplicate instances are collapsed to one."""
        instances = [protein_instance, identical_protein_instance]
        unique = collapse_to_unique_instances(instances)

        assert len(unique) == 1
        # First instance is kept as representative
        first_key = compute_uniqueness_key(protein_instance)
        assert unique[first_key].instance_id == protein_instance.instance_id

    def test_keeps_distinct_instances(self, protein_instance, different_protein_instance):
        """Distinct instances are all kept."""
        instances = [protein_instance, different_protein_instance]
        unique = collapse_to_unique_instances(instances)

        assert len(unique) == 2

    def test_empty_list(self):
        """Empty list returns empty dict."""
        unique = collapse_to_unique_instances([])
        assert unique == {}

    def test_single_instance(self, protein_instance):
        """Single instance returns dict with one entry."""
        unique = collapse_to_unique_instances([protein_instance])
        assert len(unique) == 1


class TestGroupByUniqueness:
    """Tests for grouping by uniqueness."""

    def test_groups_identical_instances(self, protein_instance, identical_protein_instance):
        """Identical instances are grouped together."""
        instances = [protein_instance, identical_protein_instance]
        groups = group_by_uniqueness(instances)

        assert len(groups) == 1
        key = compute_uniqueness_key(protein_instance)
        assert len(groups[key]) == 2

    def test_separates_different_instances(self, protein_instance, different_protein_instance):
        """Different instances are in separate groups."""
        instances = [protein_instance, different_protein_instance]
        groups = group_by_uniqueness(instances)

        assert len(groups) == 2


class TestCountUniqueByType:
    """Tests for counting unique molecules by type."""

    def test_counts_by_type(
        self,
        protein_instance,
        identical_protein_instance,
        different_protein_instance,
        water_instance,
        ion_instance,
    ):
        """Counts unique molecules per type."""
        instances = [
            protein_instance,
            identical_protein_instance,  # Duplicate of protein_instance
            different_protein_instance,  # Different protein
            water_instance,
            ion_instance,
        ]

        counts = count_unique_by_type(instances)

        assert counts["protein"] == 2  # Two unique protein sequences
        assert counts["water"] == 1
        assert counts["ion"] == 1


class TestMolecularFingerprint:
    """Tests for molecular fingerprint creation."""

    def test_fingerprint_to_key(self, protein_instance):
        """Fingerprint converts to deterministic key."""
        fp = create_fingerprint(protein_instance)
        key = fp.to_key()

        assert isinstance(key, str)
        assert len(key) > 0

    def test_fingerprint_contains_composition(self, protein_instance):
        """Fingerprint includes element composition."""
        fp = create_fingerprint(protein_instance)

        assert fp.atom_count == 100
        assert fp.residue_count == 10
        assert fp.element_composition == {"C": 50, "H": 80, "N": 10, "O": 15, "S": 2}

    def test_small_molecule_formula_hash(self):
        """Small molecules get formula hash."""
        instance = MoleculeInstance(
            instance_id="mol_INST_000006",
            atom_indices=[0, 1, 2, 3],
            residue_indices=[0],
            segment_ids=["L"],
            chain_ids=["L"],
            resids=[1],
            resnames=["ATP"],
            molecule_type=MoleculeType.SMALL_MOLECULE,
            copy_number=1,
            confidence=0.8,
            provenance={"method": "test"},
            atom_count=4,
            element_composition={"C": 10, "H": 15, "N": 5, "O": 8, "P": 3},
        )

        fp = create_fingerprint(instance)
        assert fp.formula_hash != ""
