import pytest

pytest.importorskip("MDAnalysis")
pytest.importorskip("Bio")
pytest.importorskip("numpy")

from src.signatures.signature_generators.fasta import (
    SignatureGenerationError,
    _degrees_count,
    _discontinuous_segment_cnt,
    _fragment_to_protein_sequence_verify_sequentiality,
    _mk_adjacency_matrix,
    resname_to_one_letter,
)
from src.signatures.signature_generators.fingerprint import FingerprintGenerator
from src.signatures.signature_generators.name import (
    ChainNameGenerator,
    MoleculeNameGenerator,
    SegmentNameGenerator,
)
from src.signatures.signature_generators.pdb import _pdb_atom_line


class FakeBonds:
    def __init__(self, indices):
        self.indices = list(indices)


class FakeFragment:
    def __init__(self, n_atoms=0, bonds=None):
        self.n_atoms = n_atoms
        self.bonds = FakeBonds(bonds or [])
        self.chainIDs = ["A"]
        self.moltypes = ["POPC"]
        self.segids = ["seg_0_POPC"]


def test_resname_to_one_letter_handles_protein_and_nucleic_codes():
    assert resname_to_one_letter("ALA") == "A"
    assert resname_to_one_letter("DA") == "A"
    assert resname_to_one_letter("u") == "U"


def test_resname_to_one_letter_rejects_unknown_residue():
    with pytest.raises(KeyError):
        resname_to_one_letter("UNK")


def test_sequence_adjacency_validation_accepts_single_linear_chain():
    residue_adjacency = [
        [False, True, False],
        [True, False, True],
        [False, True, False],
    ]
    atom_adjacency = [
        [False, True, False],
        [True, False, True],
        [False, True, False],
    ]

    _fragment_to_protein_sequence_verify_sequentiality(
        residue_adjacency,
        atom_adjacency,
    )


def test_sequence_adjacency_validation_rejects_disconnected_chain():
    residue_adjacency = _mk_adjacency_matrix(2)
    atom_adjacency = _mk_adjacency_matrix(2)

    assert _discontinuous_segment_cnt(residue_adjacency) == 2
    with pytest.raises(SignatureGenerationError):
        _fragment_to_protein_sequence_verify_sequentiality(
            residue_adjacency,
            atom_adjacency,
        )


def test_sequence_adjacency_validation_rejects_branched_chain():
    residue_adjacency = [
        [False, True, True, True],
        [True, False, False, False],
        [True, False, False, False],
        [True, False, False, False],
    ]
    atom_adjacency = residue_adjacency

    assert _degrees_count(residue_adjacency)[0] == 3
    with pytest.raises(SignatureGenerationError):
        _fragment_to_protein_sequence_verify_sequentiality(
            residue_adjacency,
            atom_adjacency,
        )


def test_pdb_atom_line_is_deterministic():
    line = _pdb_atom_line(
        atom_idx=1,
        atom_name="CA",
        atom_elem="C",
        residue_name="ALA",
        residue_idx=10,
        pos_x=1.0,
        pos_y=2.0,
        pos_z=3.0,
    )

    assert line == (
        "ATOM      1  CA  ALA A  10       1.000   2.000   3.000  1.00  0.00           C  "
    )


def test_fingerprint_generation_sorts_bonds_for_deterministic_output():
    generator = FingerprintGenerator()
    fragment = FakeFragment(n_atoms=3, bonds=[(2, 3), (1, 2)])

    first = generator._generate_signature(None, fragment)
    second = generator._generate_signature(None, fragment)

    assert first == second


def test_name_generators_return_configured_fragment_names():
    fragment = FakeFragment()

    assert ChainNameGenerator()._generate_signature(None, fragment) == "A"
    assert MoleculeNameGenerator()._generate_signature(None, fragment) == "POPC"
    assert SegmentNameGenerator()._generate_signature(None, fragment) == "POPC"
