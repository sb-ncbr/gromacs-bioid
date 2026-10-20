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
        mock_response.json.return_value = None
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = SequenceSignatureFetcher()
        result = fetcher.fetch("P04637", "UNIPROT_ID")
        
        assert result == "MVLSPADK"
    
    @patch("src_new.verification.fetchers.sequence_fetcher.rcsb_cache.get_cached")
    def test_sequence_fetcher_pdb(self, mock_get) -> None:
        """Mock JSON with {'entity_poly': {'pdbx_seq_one_letter_code_can': 'MVLSPADK\n'}}, assert result == 'MVLSPADK'."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "entity_poly": {"pdbx_seq_one_letter_code_can": "MVLSPADK\n"}
        }
        mock_response.text = ""
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = SequenceSignatureFetcher()
        result = fetcher.fetch("1ABC", "PDB_ID")
        
        assert result == "MVLSPADK"
    
    @patch("src_new.verification.fetchers.sequence_fetcher.rcsb_cache.get_cached")
    def test_sequence_fetcher_alphafold_returns_none(self, mock_get) -> None:
        """AlphaFold ID format should extract UniProt ID and fetch, but we test that malformed IDs return None."""
        fetcher = SequenceSignatureFetcher()
        # Malformed AlphaFold ID without proper format
        result = fetcher.fetch("INVALID", "ALPHAFOLD_ID")
        
        # Should return None due to parsing error
        assert result is None
    
    @patch("src_new.verification.fetchers.sequence_fetcher.requests.get")
    def test_sequence_fetcher_nr_id(self, mock_get) -> None:
        """Mock NCBI protein FASTA for NR_ID."""
        mock_response = Mock()
        mock_response.text = ">gi|12345|ref|NP_001| test protein\nMVLSPADK\n"
        mock_response.json.return_value = None
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = SequenceSignatureFetcher()
        result = fetcher.fetch("NP_001", "NR_ID")
        
        assert result == "MVLSPADK"
        mock_get.assert_called_once()
        assert "db=protein" in mock_get.call_args[0][0]
    
    @patch("src_new.verification.fetchers.sequence_fetcher.requests.get")
    def test_sequence_fetcher_swissprot_id(self, mock_get) -> None:
        """Mock UniProt FASTA for SWISSPROT_ID."""
        mock_response = Mock()
        mock_response.text = ">sp|P04637|TEST Test protein\nMVLSPADK\n"
        mock_response.json.return_value = None
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = SequenceSignatureFetcher()
        result = fetcher.fetch("P04637", "SWISSPROT_ID")
        
        assert result == "MVLSPADK"
    
    @patch("src_new.verification.fetchers.sequence_fetcher.requests.get")
    def test_sequence_fetcher_nt_id(self, mock_get) -> None:
        """Mock NCBI nucleotide FASTA for NT_ID."""
        mock_response = Mock()
        mock_response.text = ">NM_001123 test transcript\nATGCGTACGT\n"
        mock_response.json.return_value = None
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = SequenceSignatureFetcher()
        result = fetcher.fetch("NM_001123", "NT_ID")
        
        assert result == "ATGCGTACGT"
        mock_get.assert_called_once()
        assert "db=nuccore" in mock_get.call_args[0][0]
    
    @patch("src_new.verification.fetchers.sequence_fetcher.requests.get")
    def test_sequence_fetcher_core_nt_id(self, mock_get) -> None:
        """Mock NCBI nucleotide FASTA for CORE_NT_ID."""
        mock_response = Mock()
        mock_response.text = ">NC_000001 human chromosome\nATGCATGC\n"
        mock_response.json.return_value = None
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = SequenceSignatureFetcher()
        result = fetcher.fetch("NC_000001", "CORE_NT_ID")
        
        assert result == "ATGCATGC"
    
    def test_sequence_fetcher_supports_new_types(self) -> None:
        """Test that supports() returns True for new identifier types."""
        fetcher = SequenceSignatureFetcher()
        
        assert fetcher.supports("NR_ID") is True
        assert fetcher.supports("SWISSPROT_ID") is True
        assert fetcher.supports("NT_ID") is True
        assert fetcher.supports("CORE_NT_ID") is True
    
    @patch("src_new.verification.fetchers.sequence_fetcher.rcsb_cache.get_cached")
    def test_sequence_fetcher_pdb_entities_multi_entity(self, mock_get) -> None:
        """Test _fetch_pdb_entities with mocked multi-entity PDB response."""
        # Mock entry response with multiple polymer entities
        mock_entry_response = type('MockResponse', (), {
            'json': lambda self: {
                "rcsb_entry_container_identifiers": {
                    "polymer_entity_ids": ["1", "2"]
                }
            },
            'text': '',
            'status_code': 200,
            'raise_for_status': lambda self: None
        })()
        
        # Mock entity 1 response
        mock_entity1_response = type('MockResponse', (), {
            'json': lambda self: {
                "entity_poly": {"pdbx_seq_one_letter_code_can": "AAAA\n"}
            },
            'text': '',
            'status_code': 200,
            'raise_for_status': lambda self: None
        })()
        
        # Mock entity 2 response
        mock_entity2_response = type('MockResponse', (), {
            'json': lambda self: {
                "entity_poly": {"pdbx_seq_one_letter_code_can": "MVLSPADKT\n"}
            },
            'text': '',
            'status_code': 200,
            'raise_for_status': lambda self: None
        })()
        
        # Set up side_effect to return different responses for different URLs
        def side_effect(url, **kwargs):
            if "core/entry/" in url:
                return mock_entry_response
            elif url.endswith("/1"):
                return mock_entity1_response
            elif url.endswith("/2"):
                return mock_entity2_response
            raise ValueError(f"Unexpected URL: {url}")
        
        mock_get.side_effect = side_effect
        
        fetcher = SequenceSignatureFetcher()
        sequences = fetcher._fetch_pdb_entities("1ABC")
        
        assert len(sequences) == 2
        assert "AAAA" in sequences
        assert "MVLSPADKT" in sequences
    
    @patch("src_new.verification.fetchers.sequence_fetcher.rcsb_cache.get_cached")
    def test_sequence_fetcher_pdb_entities_empty(self, mock_get) -> None:
        """Test _fetch_pdb_entities when no polymer entities found."""
        # Mock entry response with no polymer entities
        mock_entry_response = type('MockResponse', (), {
            'json': lambda self: {
                "rcsb_entry_container_identifiers": {
                    "polymer_entity_ids": []
                }
            },
            'text': '',
            'status_code': 200,
            'raise_for_status': lambda self: None
        })()
        
        mock_get.return_value = mock_entry_response
        
        fetcher = SequenceSignatureFetcher()
        sequences = fetcher._fetch_pdb_entities("1ABC")
        
        assert sequences == []
    
    @patch("src_new.verification.fetchers.sequence_fetcher.rcsb_cache.get_cached")
    def test_sequence_fetcher_pdb_entities_with_empty_seq(self, mock_get) -> None:
        """Test _fetch_pdb_entities skips entities with empty sequences."""
        # Mock entry response with multiple polymer entities
        mock_entry_response = type('MockResponse', (), {
            'json': lambda self: {
                "rcsb_entry_container_identifiers": {
                    "polymer_entity_ids": ["1", "2"]
                }
            },
            'text': '',
            'status_code': 200,
            'raise_for_status': lambda self: None
        })()
        
        # Mock entity 1 response with empty sequence
        mock_entity1_response = type('MockResponse', (), {
            'json': lambda self: {
                "entity_poly": {"pdbx_seq_one_letter_code_can": ""}
            },
            'text': '',
            'status_code': 200,
            'raise_for_status': lambda self: None
        })()
        
        # Mock entity 2 response with valid sequence
        mock_entity2_response = type('MockResponse', (), {
            'json': lambda self: {
                "entity_poly": {"pdbx_seq_one_letter_code_can": "MVLSPADKT\n"}
            },
            'text': '',
            'status_code': 200,
            'raise_for_status': lambda self: None
        })()
        
        def side_effect(url, **kwargs):
            if "core/entry/" in url:
                return mock_entry_response
            elif url.endswith("/1"):
                return mock_entity1_response
            elif url.endswith("/2"):
                return mock_entity2_response
            raise ValueError(f"Unexpected URL: {url}")
        
        mock_get.side_effect = side_effect
        
        fetcher = SequenceSignatureFetcher()
        sequences = fetcher._fetch_pdb_entities("1ABC")
        
        # Should skip entity 1 (empty seq) and only return entity 2
        assert len(sequences) == 1
        assert sequences[0] == "MVLSPADKT"


class TestStructureFetcher:
    """Tests for StructureSignatureFetcher."""
    
    @patch("src_new.verification.fetchers.structure_fetcher.rcsb_cache.get_cached")
    def test_structure_fetcher_pdb(self, mock_get, minimal_pdb) -> None:
        """Mock response text containing the minimal PDB fixture, assert result contains 'ATOM'."""
        mock_response = Mock()
        mock_response.text = minimal_pdb
        mock_response.json.return_value = None
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        fetcher = StructureSignatureFetcher()
        result = fetcher.fetch("1ABC", "PDB_ID")
        
        assert result is not None
        assert "ATOM" in result
    
    @patch("src_new.verification.fetchers.structure_fetcher.rcsb_cache.get_cached")
    def test_structure_fetcher_alphafold_fetches_afdb(self, mock_get) -> None:
        """ALPHAFOLD_ID fetches the AFDB model (v3.138 taxonomy fix).

        Pre-v3.138 this asserted a None return, encoding the stale
        "AlphaFind hits are PDB IDs" assumption; live stage-API evidence
        (2026-10-19) shows object_id = UniProt accession, fetchable from
        AFDB — see test_alphafold_structure_chain.py for full coverage."""
        mock_response = Mock(status_code=200, text="HEADER AF\nATOM      1  N   GLY A   1\nEND\n")
        mock_get.return_value = mock_response
        
        fetcher = StructureSignatureFetcher()
        result = fetcher.fetch("AF-P04637-F1-model_v4", "ALPHAFOLD_ID")
        
        assert result == mock_response.text
        # wrapped identifier is unwrapped to the bare UniProt accession
        assert mock_get.call_args_list[0].args[0].endswith("AF-P04637-F1-model_v6.pdb")
