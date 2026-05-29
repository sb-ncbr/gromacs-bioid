"""Tests for annotation quality scorers with mocked HTTP."""

from __future__ import annotations

import pytest
from unittest.mock import patch, Mock

from src_new.verification.scorers import (
    PDBAnnotationScorer,
    UniProtAnnotationScorer,
    PubChemAnnotationScorer,
    ChemblAnnotationScorer,
    ChebiAnnotationScorer,
)


class TestPDBScorer:
    """Tests for PDBAnnotationScorer."""
    
    @patch("src_new.verification.scorers.pdb_scorer.requests.get")
    def test_pdb_scorer_basic(self, mock_get) -> None:
        """Mock RCSB JSON with resolution, r_free, method. Assert score > 50 and signals non-empty."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "rcsb_entry_info": {
                "resolution_combined": [2.0],
                "deposited_model_count": 1,
                "polymer_entity_count": 2
            },
            "refine": {"ls_rfactor_rfree": 0.25},
            "exptl": [{"method": "X-RAY DIFFRACTION"}]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        scorer = PDBAnnotationScorer()
        quality = scorer.score("1ABC", "PDB_ID")
        
        assert quality is not None
        assert quality.score > 50.0
        assert len(quality.signals) > 0
        assert quality.database == "pdb"
    
    @patch("src_new.verification.scorers.pdb_scorer.requests.get")
    def test_pdb_scorer_failure_returns_zero(self, mock_get) -> None:
        """Mock raises requests.RequestException. Assert score == 0.0, empty signals."""
        import requests
        mock_get.side_effect = requests.RequestException("Connection failed")
        
        scorer = PDBAnnotationScorer()
        quality = scorer.score("1ABC", "PDB_ID")
        
        assert quality is not None
        assert quality.score == 0.0
        assert quality.signals == []


class TestUniProtScorer:
    """Tests for UniProtAnnotationScorer."""
    
    @patch("src_new.verification.scorers.uniprot_scorer.requests.get")
    def test_uniprot_scorer_reviewed(self, mock_get) -> None:
        """Mock UniProt JSON with entryType='UniProtKB reviewed (Swiss-Prot)', annotationScore=5, etc. Assert score >= 70."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "annotationScore": 5,
            "proteinExistence": 1,
            "genes": [{"gene": {"locusName": "TP53"}}],
            "uniProtKBCrossReferences": [
                {"database": "GO", "id": "GO:0005634"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        scorer = UniProtAnnotationScorer()
        quality = scorer.score("P04637", "UNIPROT_ID")
        
        assert quality is not None
        assert quality.score >= 70.0
        assert "reviewed" in quality.signals
        assert quality.database == "uniprot"
    
    @patch("src_new.verification.scorers.uniprot_scorer.requests.get")
    def test_uniprot_scorer_unreviewed(self, mock_get) -> None:
        """Mock with TrEMBL entry, assert lower score."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "entryType": "UniProtKB unreviewed (TrEMBL)",
            "annotationScore": 2,
            "proteinExistence": 3,
            "genes": [],
            "uniProtKBCrossReferences": []
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        scorer = UniProtAnnotationScorer()
        quality = scorer.score("A0A123", "UNIPROT_ID")
        
        assert quality is not None
        # Unreviewed should have lower score than reviewed
        assert quality.score < 70.0
        assert "reviewed" not in quality.signals
    
    @patch("src_new.verification.scorers.uniprot_scorer.requests.get")
    def test_uniprot_scorer_from_alphafold_id(self, mock_get) -> None:
        """Pass 'AF-P04637-F1-model_v4', mock UniProt JSON, assert score > 0."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "annotationScore": 5,
            "proteinExistence": 1,
            "genes": [{"gene": {"locusName": "TP53"}}],
            "uniProtKBCrossReferences": []
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        scorer = UniProtAnnotationScorer()
        quality = scorer.score("AF-P04637-F1-model_v4", "ALPHAFOLD_ID")
        
        assert quality is not None
        assert quality.score > 0.0


class TestPubChemScorer:
    """Tests for PubChemAnnotationScorer."""
    
    @patch("src_new.verification.scorers.pubchem_scorer.requests.get")
    def test_pubchem_scorer_basic(self, mock_get) -> None:
        """Mock PubChem property JSON and synonyms JSON. Assert score > 0."""
        # First call: properties
        props_response = Mock()
        props_response.json.return_value = {
            "PropertyTable": {
                "Properties": [{
                    "CanonicalSMILES": "O",
                    "IsomericSMILES": "O",
                    "IUPACName": "oxidane",
                    "MolecularFormula": "H2O"
                }]
            }
        }
        props_response.raise_for_status = Mock()
        
        # Second call: synonyms
        synonyms_response = Mock()
        synonyms_response.json.return_value = {
            "InformationList": {
                "Information": [{
                    "Synonym": ["water", "dihydrogen oxide"]
                }]
            }
        }
        synonyms_response.raise_for_status = Mock()
        
        mock_get.side_effect = [props_response, synonyms_response]
        
        scorer = PubChemAnnotationScorer()
        quality = scorer.score("962", "PUBCHEM_CID")
        
        assert quality is not None
        assert quality.score > 0.0
        assert quality.database == "pubchem"


class TestChemblScorer:
    """Tests for ChemblAnnotationScorer."""
    
    @patch("src_new.verification.scorers.chembl_scorer.requests.get")
    def test_chembl_scorer_basic(self, mock_get) -> None:
        """Mock ChEMBL molecule JSON. Assert score > 0."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "molecule_structures": {
                "canonical_smiles": "CCO",
                "standard_inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
            },
            "molecule_properties": {
                "mw": 46.07
            },
            "molecule_hierarchy": {
                "parent_chembl_id": "CHEMBL25"
            },
            "pref_name": "ETHANOL"
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        scorer = ChemblAnnotationScorer()
        quality = scorer.score("CHEMBL25", "CHEMBL_ID")
        
        assert quality is not None
        assert quality.score > 0.0
        assert quality.database == "chembl"


class TestChebiScorer:
    """Tests for ChebiAnnotationScorer."""
    
    @patch("src_new.verification.scorers.chebi_scorer.requests.get")
    def test_chebi_scorer_basic(self, mock_get) -> None:
        """Mock ChEBI compound JSON with stars=3. Assert score >= 80."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "definition": "An alcohol is a primary aliphatic alcohol.",
            "default_structure": {
                "smiles": "CCO",
                "inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
            },
            "stars": 3,
            "name": "ethanol"
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        scorer = ChebiAnnotationScorer()
        quality = scorer.score("CHEBI:16236", "CHEBI_ID")
        
        assert quality is not None
        assert quality.score >= 80.0
        assert quality.database == "chebi"
        # With stars=3, should have "stars" signal and max score
        assert "stars" in quality.signals
        assert quality.score >= 100.0  # base 20 + definition 20 + smiles 20 + inchi_key 20 + stars 20 = 100
    
    @patch("src_new.verification.scorers.chebi_scorer.requests.get")
    def test_chebi_scorer_no_stars(self, mock_get) -> None:
        """Mock with stars=1. Assert lower score than stars=3."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "definition": "A test compound.",
            "default_structure": {
                "smiles": "CCO",
                "inchi_key": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
            },
            "stars": 1,
            "name": "test compound"
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        scorer = ChebiAnnotationScorer()
        quality = scorer.score("CHEBI:99999", "CHEBI_ID")
        
        assert quality is not None
        # stars=1 means not manually curated, should not have "stars" signal
        assert "stars" not in quality.signals
        # Score should be less than with stars=3 (which would be 100)
        assert quality.score < 100.0


class TestScorerUnsupportedType:
    """Tests for unsupported identifier types."""
    
    def test_pdb_scorer_unsupported_type_returns_none(self) -> None:
        """Call with wrong ident_type, assert None."""
        scorer = PDBAnnotationScorer()
        result = scorer.score("P04637", "UNIPROT_ID")
        assert result is None
    
    def test_uniprot_scorer_unsupported_type_returns_none(self) -> None:
        """Call with wrong ident_type, assert None."""
        scorer = UniProtAnnotationScorer()
        result = scorer.score("1ABC", "PDB_ID")
        assert result is None
    
    def test_pubchem_scorer_unsupported_type_returns_none(self) -> None:
        """Call with wrong ident_type, assert None."""
        scorer = PubChemAnnotationScorer()
        result = scorer.score("1ABC", "PDB_ID")
        assert result is None
    
    def test_chembl_scorer_unsupported_type_returns_none(self) -> None:
        """Call with wrong ident_type, assert None."""
        scorer = ChemblAnnotationScorer()
        result = scorer.score("P04637", "UNIPROT_ID")
        assert result is None
    
    def test_chebi_scorer_unsupported_type_returns_none(self) -> None:
        """Call with wrong ident_type, assert None."""
        scorer = ChebiAnnotationScorer()
        result = scorer.score("962", "PUBCHEM_CID")
        assert result is None
