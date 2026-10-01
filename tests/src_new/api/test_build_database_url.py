"""Unit tests for the build_database_url helper in src_new.api.utils."""

import pytest

from src_new.api.utils import build_database_url, normalize_identifier


class TestPdbChainStrip:
    """PDB identifiers should have chain suffix stripped and be uppercased."""

    def test_uppercase_with_chain(self):
        assert build_database_url("1HRC_A", "PDB_ID") == "https://www.rcsb.org/structure/1HRC"

    def test_lowercase_with_chain(self):
        assert build_database_url("1hrc_a", "pdb_id") == "https://www.rcsb.org/structure/1HRC"

    def test_uppercase_no_chain(self):
        assert build_database_url("4ZZZ", "PDB_ID") == "https://www.rcsb.org/structure/4ZZZ"

    def test_lowercase_no_chain(self):
        assert build_database_url("4zzz", "pdb_id") == "https://www.rcsb.org/structure/4ZZZ"

    def test_different_chain_letter(self):
        assert build_database_url("4ZZZ_B", "PDB_ID") == "https://www.rcsb.org/structure/4ZZZ"


class TestChemblPrefix:
    """CHEMBL bare digits should get CHEMBL prefix and use explore URL."""

    def test_bare_digits(self):
        assert build_database_url("12345", "CHEMBL_ID") == (
            "https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL12345"
        )

    def test_already_prefixed(self):
        assert build_database_url("CHEMBL276", "CHEMBL") == (
            "https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL276"
        )

    def test_lowercase_bare_digits(self):
        assert build_database_url("6801", "chembl_id") == (
            "https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL6801"
        )


class TestPubchemPassthrough:
    """PubChem identifiers should pass through unchanged."""

    def test_pubchem_cid(self):
        assert build_database_url("12345", "PUBCHEM_CID") == (
            "https://pubchem.ncbi.nlm.nih.gov/compound/12345"
        )

    def test_pubchem_short_name(self):
        assert build_database_url("789", "PUBCHEM") == (
            "https://pubchem.ncbi.nlm.nih.gov/compound/789"
        )


class TestNoneAndEmpty:
    """None or empty identifiers should return None safely."""

    def test_none_identifier(self):
        assert build_database_url(None, "PDB_ID") is None

    def test_empty_string(self):
        assert build_database_url("", "PDB_ID") is None

    def test_whitespace_only(self):
        assert build_database_url("   ", "PDB_ID") is None

    def test_none_ident_type(self):
        assert build_database_url("1HRC", None) is None


class TestOtherTypes:
    """Other identifier types should remain unchanged."""

    def test_uniprot(self):
        assert build_database_url("P12345", "UNIPROT_ID") == (
            "https://www.uniprot.org/uniprotkb/P12345"
        )

    def test_chebi(self):
        assert build_database_url("CHEBI:15377", "CHEBI_ID") == (
            "https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:15377"
        )

    def test_alphafold(self):
        assert build_database_url("A0A123", "ALPHAFOLD_ID") == (
            "https://alphafold.ebi.ac.uk/entry/A0A123"
        )

    def test_unknown_type(self):
        assert build_database_url("ABC", "SOME_UNKNOWN_TYPE") is None
