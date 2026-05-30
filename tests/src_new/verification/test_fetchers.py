"""Tests for signature fetchers with mocked HTTP."""

from __future__ import annotations

import pytest
from unittest.mock import patch, Mock

from src_new.verification.fetchers import (
    CompoundSignatureFetcher,
    SequenceSignatureFetcher,
    StructureSignatureFetcher,
)


class TestCompoundFetcher:
    """Tests for CompoundSignatureFetcher."""
    
    @patch("src_new.verification.fetchers.compound_fetcher.requests.get")
    def test_compound_fetcher_pubchem(self, mock_get) -> None:
        """Mock response text 'CCO', call fetch('962', 'PUBCHEM_CID'), assert result == 'CCO'."""
        mock_response = Mock()
        mock_response.text = "CCO"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = CompoundSignatureFetcher()
        result = fetcher.fetch("962", "PUBCHEM_CID")
        
        assert result == "CCO"
        mock_get.assert_called_once()
    
    @patch("src_new.verification.fetchers.compound_fetcher.requests.get")
    def test_compound_fetcher_chembl(self, mock_get) -> None:
        """Mock JSON with {'molecule_structures': {'canonical_smiles': 'CCO'}}, assert result == 'CCO'."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "molecule_structures": {"canonical_smiles": "CCO"}
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = CompoundSignatureFetcher()
        result = fetcher.fetch("25", "CHEMBL_ID")
        
        assert result == "CCO"
    
    @patch("src_new.verification.fetchers.compound_fetcher.requests.get")
    def test_compound_fetcher_chebi(self, mock_get) -> None:
        """Mock JSON with {'default_structure': {'smiles': 'CCO'}}, assert result == 'CCO'."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "default_structure": {"smiles": "CCO"}
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = CompoundSignatureFetcher()
        result = fetcher.fetch("16236", "CHEBI_ID")
        
        assert result == "CCO"
    
    def test_compound_fetcher_unsupported_type(self) -> None:
        """Call with 'UNIPROT_ID', assert None."""
        fetcher = CompoundSignatureFetcher()
        result = fetcher.fetch("P04637", "UNIPROT_ID")
        
        assert result is None


class TestSequenceFetcher:
    """Tests for SequenceSignatureFetcher."""
    
    @patch("src_new.verification.fetchers.sequence_fetcher.requests.get")
    def test_sequence_fetcher_uniprot(self, mock_get) -> None:
        """Mock FASTA text '>sp|P04637|TEST\nMVLSPADK\n', assert result == 'MVLSPADK'."""
        mock_response = Mock()
        mock_response.text = ">sp|P04637|TEST\nMVLSPADK\n"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = SequenceSignatureFetcher()
        result = fetcher.fetch("P04637", "UNIPROT_ID")
        
        assert result == "MVLSPADK"
    
    @patch("src_new.verification.fetchers.sequence_fetcher.requests.get")
    def test_sequence_fetcher_pdb(self, mock_get) -> None:
        """Mock JSON with {'entity_poly': {'pdbx_seq_one_letter_code_can': 'MVLSPADK\n'}}, assert result == 'MVLSPADK'."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "entity_poly": {"pdbx_seq_one_letter_code_can": "MVLSPADK\n"}
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = SequenceSignatureFetcher()
        result = fetcher.fetch("1ABC", "PDB_ID")
        
        assert result == "MVLSPADK"
    
    @patch("src_new.verification.fetchers.sequence_fetcher.requests.get")
    def test_sequence_fetcher_alphafold_returns_none(self, mock_get) -> None:
        """AlphaFold ID format should extract UniProt ID and fetch, but we test that malformed IDs return None."""
        fetcher = SequenceSignatureFetcher()
        # Malformed AlphaFold ID without proper format
        result = fetcher.fetch("INVALID", "ALPHAFOLD_ID")
        
        # Should return None due to parsing error
        assert result is None


class TestStructureFetcher:
    """Tests for StructureSignatureFetcher."""
    
    @patch("src_new.verification.fetchers.structure_fetcher.requests.get")
    def test_structure_fetcher_pdb(self, mock_get, minimal_pdb) -> None:
        """Mock response text containing the minimal PDB fixture, assert result contains 'ATOM'."""
        mock_response = Mock()
        mock_response.text = minimal_pdb
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = StructureSignatureFetcher()
        result = fetcher.fetch("1ABC", "PDB_ID")
        
        assert result is not None
        assert "ATOM" in result
    
    @patch("src_new.verification.fetchers.structure_fetcher.requests.get")
    def test_structure_fetcher_alphafold_returns_none(self, mock_get) -> None:
        """ALPHAFOLD_ID returns None."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = StructureSignatureFetcher()
        result = fetcher.fetch("AF-P04637-F1-model_v4", "ALPHAFOLD_ID")
        
        assert result is None
