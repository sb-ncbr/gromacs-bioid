import sys
import types

if "MDAnalysis" not in sys.modules:
    mdanalysis = types.ModuleType("MDAnalysis")
    mdanalysis.Universe = type("Universe", (), {})
    mdanalysis.AtomGroup = type("AtomGroup", (), {})
    sys.modules["MDAnalysis"] = mdanalysis

if "periodictable" not in sys.modules:
    periodictable = types.ModuleType("periodictable")
    periodictable.elements = []
    sys.modules["periodictable"] = periodictable

if "rdkit" not in sys.modules:
    rdkit = types.ModuleType("rdkit")
    chem = types.ModuleType("rdkit.Chem")
    determine_bonds = types.ModuleType("rdkit.Chem.rdDetermineBonds")
    chem.rdDetermineBonds = determine_bonds
    rdkit.Chem = chem
    sys.modules["rdkit"] = rdkit
    sys.modules["rdkit.Chem"] = chem
    sys.modules["rdkit.Chem.rdDetermineBonds"] = determine_bonds

from ... import src as project_src

sys.modules.setdefault("src", project_src)

from ...src.verifier.verification_workers.verification_core import (
    VerificationKind,
    VerificationWorker,
    Verifier,
)


class FakeResults:
    def __init__(self, data):
        self.data = data

    def get_item(self, path, default=None):
        current = self.data
        for part in path.split("/"):
            if not isinstance(current, dict) or part not in current:
                if default is not None:
                    return default
                raise KeyError(path)
            current = current[part]
        return current


class StaticWorker(VerificationWorker):
    def __init__(self, scores):
        self.scores = scores

    def verify_identification(self, ident, ident_type, signature):
        return self.scores.get(ident)


def make_verifier(data, kind=VerificationKind.NONE, worker=None):
    return Verifier(
        simulation=None,
        results=FakeResults(data),
        fragment_name="Protein",
        verification_kind=kind,
        worker=worker,
    )


def test_get_identifiers_sorts_by_reported_confidence():
    verifier = make_verifier(
        {
            "identifiers": {
                "Protein": {
                    "FASTA_MAP_PROTEIN": {
                        "attempted": ["BLAST_PDB_PROT"],
                        "BLAST_PDB_PROT": {
                            "hit_type": "PDB_ID",
                            "hits": [("low", 40.0), ("high", "95.0")],
                        },
                    }
                }
            }
        }
    )

    assert verifier.get_identifiers() == [
        ("high", "PDB_ID", 95.0),
        ("low", "PDB_ID", 40.0),
    ]


def test_no_candidate_returns_empty_list():
    verifier = make_verifier({"identifiers": {"Protein": {"FASTA_MAP_PROTEIN": {"attempted": []}}}})

    assert verifier.get_identifiers() == []
    assert verifier.calculate_identifier_confidence() == []


def test_none_verification_preserves_equivalent_candidates():
    verifier = make_verifier(
        {
            "identifiers": {
                "Protein": {
                    "FASTA_MAP_PROTEIN": {
                        "BLAST_PDB_PROT": {
                            "hit_type": "PDB_ID",
                            "hits": [("1AAA", 100.0), ("2BBB", 100.0)],
                        }
                    }
                }
            }
        }
    )

    assert verifier.calculate_identifier_confidence() == [
        ("1AAA", "PDB_ID", 100.0, None),
        ("2BBB", "PDB_ID", 100.0, None),
    ]


def test_verified_candidates_rank_by_observed_confidence():
    verifier = make_verifier(
        {
            "signatures": {
                "Protein": {
                    "generated": {
                        "FASTA_MAP_PROTEIN": "MAGA",
                    }
                }
            },
            "identifiers": {
                "Protein": {
                    "FASTA_MAP_PROTEIN": {
                        "BLAST_PDB_PROT": {
                            "hit_type": "PDB_ID",
                            "hits": [("reported_best", 99.0), ("verified_best", 90.0)],
                        }
                    }
                }
            },
        },
        kind=VerificationKind.PROTEIN,
        worker=StaticWorker({"reported_best": 10.0, "verified_best": 95.0}),
    )

    assert verifier.calculate_identifier_confidence() == [
        ("verified_best", "PDB_ID", 90.0, 95.0),
        ("reported_best", "PDB_ID", 99.0, 10.0),
    ]


def test_failed_reverse_validation_preserves_candidate_with_no_observed_confidence():
    verifier = make_verifier(
        {
            "signatures": {
                "Protein": {
                    "generated": {
                        "FASTA_MAP_PROTEIN": "MAGA",
                    }
                }
            },
            "identifiers": {
                "Protein": {
                    "FASTA_MAP_PROTEIN": {
                        "BLAST_PDB_PROT": {
                            "hit_type": "PDB_ID",
                            "hits": [("unverified", 80.0)],
                        }
                    }
                }
            },
        },
        kind=VerificationKind.PROTEIN,
        worker=StaticWorker({"unverified": None}),
    )

    assert verifier.calculate_identifier_confidence() == [
        ("unverified", "PDB_ID", 80.0, None),
    ]


def test_water_and_atom_have_fixed_confidence_paths():
    water = make_verifier({"identifiers": {"Protein": {}}}, kind=VerificationKind.WATER)
    assert water.calculate_identifier_confidence() == [("962", "PUBCHEM_CID", 100.0, 100.0)]

    atom = make_verifier(
        {
            "identifiers": {
                "Protein": {
                    "ATOM": {
                        "ATOM": {
                            "hit_type": "ELEMENT",
                            "hits": [("Na", 100.0)],
                        }
                    }
                }
            }
        },
        kind=VerificationKind.ATOM,
    )
    assert atom.calculate_identifier_confidence() == [("Na", "ELEMENT", 100.0, 100.0)]
