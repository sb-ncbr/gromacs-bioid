"""Shared pytest fixtures for verification tests."""

from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager
from src_new.verification.registry import get_default_registry
from src_new.verification.manager import VerificationManager


@pytest.fixture
def config() -> RunConfig:
    """Create a default RunConfig for tests."""
    return RunConfig()


@pytest.fixture
def registry(config: RunConfig):
    """Create a default verification registry."""
    return get_default_registry()


@pytest.fixture
def manager(config: RunConfig, registry):
    """Create a VerificationManager instance."""
    return VerificationManager(config, registry)


@pytest.fixture
def tmp_results(tmp_path):
    """Create a ResultsManager with a temp file."""
    results_path = tmp_path / "results.json"
    return ResultsManager(results_path)


@pytest.fixture
def minimal_pdb() -> str:
    """Return a minimal PDB-formatted string for a 3-residue peptide (ALA-GLY-SER)."""
    return """HEADER    TEST
ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N
ATOM      2  CA  ALA A   1      10.500  10.500  10.500  1.00  0.00           C
ATOM      3  C   ALA A   1      11.000  11.000  11.000  1.00  0.00           C
ATOM      4  O   ALA A   1      11.500  11.500  11.500  1.00  0.00           O
ATOM      5  N   GLY A   2      12.000  12.000  12.000  1.00  0.00           N
ATOM      6  CA  GLY A   2      12.500  12.500  12.500  1.00  0.00           C
ATOM      7  C   GLY A   2      13.000  13.000  13.000  1.00  0.00           C
ATOM      8  O   GLY A   2      13.500  13.500  13.500  1.00  0.00           O
ATOM      9  N   SER A   3      14.000  14.000  14.000  1.00  0.00           N
ATOM     10  CA  SER A   3      14.500  14.500  14.500  1.00  0.00           C
ATOM     11  C   SER A   3      15.000  15.000  15.000  1.00  0.00           C
ATOM     12  O   SER A   3      15.500  15.500  15.500  1.00  0.00           O
END
"""


@pytest.fixture
def identification_results(tmp_results: ResultsManager) -> ResultsManager:
    """Populate ResultsManager with synthetic identification data for two segments.
    
    - Segment "seg_compound": one resolver (pubchem_struct) with identity hit "962" (PUBCHEM_CID)
      from smiles generator with signature "O"
    - Segment "seg_protein": one resolver (blast_uniprot) with similarity hit ("P04637", 95.0)
      (UNIPROT_ID) from fasta_map_protein generator with signature of beta-globin
    """
    # Compound segment: identity hit from pubchem_struct
    compound_data = {
        "smiles": {
            "pubchem_struct": {
                "signature": "O",
                "hit_type": "identity",
                "ident_type": "PUBCHEM_CID",
                "hits": ["962"]
            }
        }
    }
    tmp_results.set_data("identifiers/seg_compound", compound_data)
    
    # Protein segment: similarity hit from blast_uniprot
    # Beta-globin sequence (full length human beta-globin)
    beta_globin_seq = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"
    protein_data = {
        "fasta_map_protein": {
            "blast_uniprot": {
                "signature": beta_globin_seq,
                "hit_type": "similarity",
                "ident_type": "UNIPROT_ID",
                "hits": [["P04637", 95.0]]
            }
        }
    }
    tmp_results.set_data("identifiers/seg_protein", protein_data)
    
    return tmp_results
