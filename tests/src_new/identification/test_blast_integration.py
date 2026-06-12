"""Comprehensive test suite for BLAST sequence search implementation."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.blast import (
    BLASTResolver,
    BLASTResolverPDBAA,
    BLASTResolverPDBNT,
    BLASTResolverUNIPROT,
    BLASTResolverNR,
    BLASTResolverSWISSPROT,
    BlastHit,
)
from src_new.identification.base import IdentifierResolutionError


# =============================================================================
# Fixtures and Helper Functions
# =============================================================================

@pytest.fixture
def config(tmp_path: Path) -> RunConfig:
    """Create a default RunConfig with realistic DB paths under tmp_path."""
    cfg = RunConfig()
    databases = tmp_path / "databases"
    databases.mkdir(parents=True, exist_ok=True)
    
    # Set all DB paths to something realistic under tmp_path
    cfg.blast.pdb_aa_db = str(databases / "pdbaa")
    cfg.blast.pdb_nt_db = str(databases / "pdbnt")
    cfg.blast.uniprot_aa_db = str(databases / "swissprot")
    cfg.blast.nr_aa_db = str(databases / "nr")
    cfg.blast.swissprot_aa_db = str(databases / "swissprot")
    return cfg


def make_blast_json(hits: list[dict], query_len: int = 100) -> list[dict]:
    """Build realistic BLAST outfmt 15 JSON structure."""
    return [{
        "BlastOutput2": {
            "report": {
                "results": {
                    "search": {
                        "query_len": query_len,
                        "hits": hits
                    }
                }
            }
        }
    }]


def make_hit(
    accessions: list[str],
    identity: int,
    align_len: int,
    bits: float,
    evalue: float
) -> dict:
    """Create a single BLAST hit dictionary."""
    return {
        "description": [{"accession": acc} for acc in accessions],
        "hsps": [{
            "identity": identity,
            "align_len": align_len,
            "bit_score": bits,
            "evalue": evalue
        }]
    }


# =============================================================================
# Test Class: TestBlastHitParsing
# =============================================================================

class TestBlastHitParsing:
    """Test _process_blast_results with real-looking BLAST JSON output."""

    def test_parse_single_hit(self, config: RunConfig) -> None:
        """Test parsing one hit with clear values."""
        resolver = BLASTResolverPDBAA(config)
        
        # Query len=100, align_len=100, identity=99, bits=200, evalue=1e-100
        hits = [make_hit(
            accessions=["1A2B_A"],
            identity=99,
            align_len=100,
            bits=200.0,
            evalue=1e-100
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        results = resolver._process_blast_results(json_data)
        
        assert len(results) == 1
        hit = results[0]
        assert hit.accessions == ["1A2B_A"]
        assert hit.evalue == 1e-100
        assert hit.bits == 200.0
        assert hit.identity_p == 0.99  # 99/100
        assert hit.coverage_p == 1.0    # 100/100

    def test_parse_multiple_hits(self, config: RunConfig) -> None:
        """Test parsing multiple hits, all returned in list."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [
            make_hit(["1A2B_A"], identity=99, align_len=100, bits=200.0, evalue=1e-100),
            make_hit(["3C4D_B"], identity=85, align_len=90, bits=150.0, evalue=1e-50),
            make_hit(["5E6F_C"], identity=70, align_len=80, bits=100.0, evalue=1e-20),
        ]
        json_data = make_blast_json(hits, query_len=100)
        
        results = resolver._process_blast_results(json_data)
        
        assert len(results) == 3
        assert results[0].accessions == ["1A2B_A"]
        assert results[1].accessions == ["3C4D_B"]
        assert results[2].accessions == ["5E6F_C"]

    def test_parse_hit_with_multiple_accessions(self, config: RunConfig) -> None:
        """Test parsing one hit with 2 accessions in description."""
        resolver = BLASTResolverPDBAA(config)
        
        # Single hit with multiple accessions
        hit = {
            "description": [
                {"accession": "1A2B_A"},
                {"accession": "1A2B_B"}
            ],
            "hsps": [{
                "identity": 95,
                "align_len": 100,
                "bit_score": 180.0,
                "evalue": 1e-80
            }]
        }
        json_data = make_blast_json([hit], query_len=100)
        
        results = resolver._process_blast_results(json_data)
        
        assert len(results) == 1
        assert results[0].accessions == ["1A2B_A", "1A2B_B"]
        assert results[0].identity_p == 0.95
        assert results[0].coverage_p == 1.0

    def test_parse_no_hits(self, config: RunConfig) -> None:
        """Test empty hits array returns []."""
        resolver = BLASTResolverPDBAA(config)
        
        json_data = make_blast_json([], query_len=100)
        
        results = resolver._process_blast_results(json_data)
        
        assert results == []

    def test_parse_missing_blastoutput2(self, config: RunConfig) -> None:
        """Test missing BlastOutput2 key returns []."""
        resolver = BLASTResolverPDBAA(config)
        
        json_data = [{"some_other_key": "value"}]
        
        results = resolver._process_blast_results(json_data)
        
        assert results == []

    def test_parse_malformed_no_report(self, config: RunConfig) -> None:
        """Test malformed JSON without report section returns []."""
        resolver = BLASTResolverPDBAA(config)
        
        json_data = [{
            "BlastOutput2": {
                "something": "else"
            }
        }]
        
        results = resolver._process_blast_results(json_data)
        
        assert results == []

    def test_parse_zero_aligned_residues(self, config: RunConfig) -> None:
        """Test identity_p should be 0.0 when align_len is 0 (division by zero guard)."""
        resolver = BLASTResolverPDBAA(config)
        
        hit = {
            "description": [{"accession": "1A2B_A"}],
            "hsps": [{
                "identity": 0,
                "align_len": 0,
                "bit_score": 0.0,
                "evalue": 1.0
            }]
        }
        json_data = make_blast_json([hit], query_len=100)
        
        results = resolver._process_blast_results(json_data)
        
        assert len(results) == 1
        assert results[0].identity_p == 0.0  # Guard against division by zero

    def test_parse_zero_query_len(self, config: RunConfig) -> None:
        """Test coverage_p should be 0.0 when query_len is 0 (division by zero guard)."""
        resolver = BLASTResolverPDBAA(config)
        
        hit = {
            "description": [{"accession": "1A2B_A"}],
            "hsps": [{
                "identity": 50,
                "align_len": 50,
                "bit_score": 100.0,
                "evalue": 1e-10
            }]
        }
        json_data = make_blast_json([hit], query_len=0)
        
        results = resolver._process_blast_results(json_data)
        
        assert len(results) == 1
        assert results[0].coverage_p == 0.0  # Guard against division by zero


# =============================================================================
# Test Class: TestBlastIdentityFiltering
# =============================================================================

class TestBlastIdentityFiltering:
    """Test _run_blast_identity filtering with mocked BLAST output."""

    def test_identity_passes_all_thresholds(self, config: RunConfig) -> None:
        """Hit with evalue=1e-100, bits=200, identity_p=1.0, coverage_p=1.0 -> included."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["PERFECT_HIT"],
            identity=100,
            align_len=100,
            bits=200.0,
            evalue=1e-100
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_identity("SEQUENCE", "")
        
        assert result == ["PERFECT_HIT"]

    def test_identity_fails_evalue(self, config: RunConfig) -> None:
        """evalue=0.5 (> 1e-50) -> excluded."""
        resolver = BLASTResolverPDBAA(config)
        
        # Perfect except evalue is too high
        hits = [make_hit(
            accessions=["BAD_EVALUE"],
            identity=100,
            align_len=100,
            bits=200.0,
            evalue=0.5  # Much higher than 1e-50 threshold
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_identity("SEQUENCE", "")
        
        assert result == []

    def test_identity_fails_bits(self, config: RunConfig) -> None:
        """bits=30 (< 51) -> excluded."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["LOW_BITS"],
            identity=100,
            align_len=100,
            bits=30.0,  # Below 51 threshold
            evalue=1e-100
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_identity("SEQUENCE", "")
        
        assert result == []

    def test_identity_fails_identity(self, config: RunConfig) -> None:
        """identity_p=0.95 (< 0.99) -> excluded."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["LOW_IDENTITY"],
            identity=95,  # 95/100 = 0.95, below 0.99 threshold
            align_len=100,
            bits=200.0,
            evalue=1e-100
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_identity("SEQUENCE", "")
        
        assert result == []

    def test_identity_fails_coverage(self, config: RunConfig) -> None:
        """coverage_p=0.90 (< 0.99) -> excluded."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["LOW_COVERAGE"],
            identity=99,
            align_len=90,  # 90/100 = 0.90, below 0.99 threshold
            bits=200.0,
            evalue=1e-100
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_identity("SEQUENCE", "")
        
        assert result == []

    def test_identity_borderline_exact(self, config: RunConfig) -> None:
        """identity_p=0.99, coverage_p=0.99 exactly -> included (use <=/>=)."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["BORDERLINE_EXACT"],
            identity=99,  # 99/100 = 0.99 exactly
            align_len=100,
            bits=51.0,    # Exactly at threshold
            evalue=1e-50  # Exactly at threshold
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_identity("SEQUENCE", "")
        
        assert result == ["BORDERLINE_EXACT"]

    def test_identity_only_perfect_matches(self, config: RunConfig) -> None:
        """Mix of perfect and imperfect hits, only perfect returned."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [
            # Perfect hit - should pass
            make_hit(["PERFECT"], identity=100, align_len=100, bits=200.0, evalue=1e-100),
            # Imperfect hits - should fail
            make_hit(["LOW_ID"], identity=95, align_len=100, bits=200.0, evalue=1e-100),
            make_hit(["LOW_COV"], identity=100, align_len=90, bits=200.0, evalue=1e-100),
            make_hit(["HIGH_EVAL"], identity=100, align_len=100, bits=200.0, evalue=0.5),
        ]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_identity("SEQUENCE", "")
        
        assert result == ["PERFECT"]


# =============================================================================
# Test Class: TestBlastSimilarityFiltering
# =============================================================================

class TestBlastSimilarityFiltering:
    """Test _run_blast_similarity filtering with mocked BLAST output."""

    def test_similarity_passes_all_thresholds(self, config: RunConfig) -> None:
        """evalue=1e-5, bits=50, identity_p=1.0, coverage_p=0.5 -> included."""
        resolver = BLASTResolverPDBAA(config)
    
        hits = [make_hit(
            accessions=["GOOD_SIMILARITY"],
            identity=50,  # 50/50 = 1.0
            align_len=50,  # 50/100 = 0.5 coverage
            bits=50.0,
            evalue=1e-5
        )]
        json_data = make_blast_json(hits, query_len=100)
    
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_similarity("SEQUENCE", "")
    
        assert len(result) == 1
        assert result[0][0] == "GOOD_SIMILARITY"
        assert result[0][1] == 100.0  # identity_p * 100 = 1.0 * 100
    
    def test_similarity_fails_evalue(self, config: RunConfig) -> None:
        """evalue=0.5 (> 0.1) -> excluded."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["BAD_EVALUE"],
            identity=50,
            align_len=50,
            bits=50.0,
            evalue=0.5  # Much higher than 0.1 threshold
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_similarity("SEQUENCE", "")
        
        assert result == []

    def test_similarity_fails_bits(self, config: RunConfig) -> None:
        """bits=10 (< 20) -> excluded."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["LOW_BITS"],
            identity=50,
            align_len=50,
            bits=10.0,  # Below 20 threshold
            evalue=1e-5
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_similarity("SEQUENCE", "")
        
        assert result == []

    def test_similarity_fails_identity(self, config: RunConfig) -> None:
        """identity_p=0.30 (< 0.4) -> excluded."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["LOW_IDENTITY"],
            identity=30,  # 30/100 = 0.30, below 0.4 threshold
            align_len=100,
            bits=50.0,
            evalue=1e-5
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_similarity("SEQUENCE", "")
        
        assert result == []

    def test_similarity_fails_coverage(self, config: RunConfig) -> None:
        """coverage_p=0.10 (< 0.15) -> excluded."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["LOW_COVERAGE"],
            identity=50,
            align_len=10,  # 10/100 = 0.10, below 0.15 threshold
            bits=50.0,
            evalue=1e-5
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_similarity("SEQUENCE", "")
        
        assert result == []

    def test_similarity_returns_percentage_score(self, config: RunConfig) -> None:
        """Verify returned score is identity_p * 100 (e.g., 0.75 -> 75.0)."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["SCORE_TEST"],
            identity=75,  # 75/100 = 0.75
            align_len=100,
            bits=50.0,
            evalue=1e-5
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_similarity("SEQUENCE", "")
        
        assert len(result) == 1
        assert result[0][1] == 75.0  # 0.75 * 100

    def test_similarity_includes_borderline(self, config: RunConfig) -> None:
        """identity_p=0.40 exactly -> included."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["BORDERLINE_ID"],
            identity=40,  # 40/100 = 0.40 exactly
            align_len=100,
            bits=20.0,    # Exactly at bits threshold
            evalue=0.1    # Exactly at evalue threshold
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            result = resolver._run_blast_similarity("SEQUENCE", "")
        
        assert result == [("BORDERLINE_ID", 40.0)]


# =============================================================================
# Test Class: TestBlastResolverClasses
# =============================================================================

class TestBlastResolverClasses:
    """Test all 5 resolver subclasses for correct configuration."""

    def test_pdbaa_has_correct_attributes(self, config: RunConfig) -> None:
        """Test PDBAA has correct db_path, is_protein, resolver_name, identifier_type."""
        config.blast.pdb_aa_db = "/test/pdbaa"
        resolver = BLASTResolverPDBAA(config)
        
        assert resolver.db_path == "/test/pdbaa"
        assert resolver.is_protein is True
        assert resolver.name == "blast_pdb_protein"
        assert resolver.identifier_type == "PDB_ID"
        assert resolver.accepted_signatures == ["residue_sequence_protein"]

    def test_pdbaa_uses_correct_executable(self, config: RunConfig) -> None:
        """Test PDBAA uses blastp for protein."""
        resolver = BLASTResolverPDBAA(config)
        assert resolver._get_exec_path() == config.blast.blastp_exec

    def test_pdbaa_accepted_signatures(self, config: RunConfig) -> None:
        """Test PDBAA accepts residue_sequence_protein."""
        resolver = BLASTResolverPDBAA(config)
        assert resolver.accepted_signatures == ["residue_sequence_protein"]

    def test_pdbnt_has_correct_attributes(self, config: RunConfig) -> None:
        """Test PDBNT has correct attributes."""
        config.blast.pdb_nt_db = "/test/pdbnt"
        resolver = BLASTResolverPDBNT(config)
        
        assert resolver.db_path == "/test/pdbnt"
        assert resolver.is_protein is False
        assert resolver.name == "blast_pdb_nucleic"
        assert resolver.identifier_type == "PDB_ID"
        assert resolver.accepted_signatures == ["residue_sequence_nucleotide"]

    def test_pdbnt_uses_correct_executable(self, config: RunConfig) -> None:
        """Test PDBNT uses blastn for nucleotide."""
        resolver = BLASTResolverPDBNT(config)
        assert resolver._get_exec_path() == config.blast.blastn_exec

    def test_pdbnt_accepted_signatures(self, config: RunConfig) -> None:
        """Test PDBNT accepts residue_sequence_nucleotide."""
        resolver = BLASTResolverPDBNT(config)
        assert resolver.accepted_signatures == ["residue_sequence_nucleotide"]

    def test_uniprot_has_correct_attributes(self, config: RunConfig) -> None:
        """Test UNIPROT has correct attributes."""
        config.blast.uniprot_aa_db = "/test/uniprot"
        resolver = BLASTResolverUNIPROT(config)
        
        assert resolver.db_path == "/test/uniprot"
        assert resolver.is_protein is True
        assert resolver.name == "blast_uniprot"
        assert resolver.identifier_type == "UNIPROT_ID"
        assert resolver.accepted_signatures == ["residue_sequence_protein"]

    def test_uniprot_uses_correct_executable(self, config: RunConfig) -> None:
        """Test UNIPROT uses blastp for protein."""
        resolver = BLASTResolverUNIPROT(config)
        assert resolver._get_exec_path() == config.blast.blastp_exec

    def test_uniprot_accepted_signatures(self, config: RunConfig) -> None:
        """Test UNIPROT accepts residue_sequence_protein."""
        resolver = BLASTResolverUNIPROT(config)
        assert resolver.accepted_signatures == ["residue_sequence_protein"]

    def test_nr_has_correct_attributes(self, config: RunConfig) -> None:
        """Test NR has correct attributes."""
        config.blast.nr_aa_db = "/test/nr"
        resolver = BLASTResolverNR(config)
        
        assert resolver.db_path == "/test/nr"
        assert resolver.is_protein is True
        assert resolver.name == "blast_nr_protein"
        assert resolver.identifier_type == "NR_ID"
        assert resolver.accepted_signatures == ["residue_sequence_protein"]

    def test_nr_uses_correct_executable(self, config: RunConfig) -> None:
        """Test NR uses blastp for protein."""
        resolver = BLASTResolverNR(config)
        assert resolver._get_exec_path() == config.blast.blastp_exec

    def test_nr_accepted_signatures(self, config: RunConfig) -> None:
        """Test NR accepts residue_sequence_protein."""
        resolver = BLASTResolverNR(config)
        assert resolver.accepted_signatures == ["residue_sequence_protein"]

    def test_swissprot_has_correct_attributes(self, config: RunConfig) -> None:
        """Test SWISSPROT has correct attributes."""
        config.blast.swissprot_aa_db = "/test/swissprot"
        resolver = BLASTResolverSWISSPROT(config)
        
        assert resolver.db_path == "/test/swissprot"
        assert resolver.is_protein is True
        assert resolver.name == "blast_swissprot_protein"
        assert resolver.identifier_type == "SWISSPROT_ID"
        assert resolver.accepted_signatures == ["residue_sequence_protein"]

    def test_swissprot_uses_correct_executable(self, config: RunConfig) -> None:
        """Test SWISSPROT uses blastp for protein."""
        resolver = BLASTResolverSWISSPROT(config)
        assert resolver._get_exec_path() == config.blast.blastp_exec

    def test_swissprot_accepted_signatures(self, config: RunConfig) -> None:
        """Test SWISSPROT accepts residue_sequence_protein."""
        resolver = BLASTResolverSWISSPROT(config)
        assert resolver.accepted_signatures == ["residue_sequence_protein"]

    def test_uniprot_uses_swissprot_fallback(self, config: RunConfig) -> None:
        """Test UNIPROT falls back to swissprot_aa_db when uniprot_aa_db is empty."""
        config.blast.uniprot_aa_db = ""
        config.blast.swissprot_aa_db = "/test/swissprot_fallback"
        resolver = BLASTResolverUNIPROT(config)
        
        assert resolver.db_path == "/test/swissprot_fallback"


# =============================================================================
# Test Class: TestBlastPreflight
# =============================================================================

class TestBlastPreflight:
    """Tests for preflight checks (empty/missing database paths)."""

    def test_preflight_empty_db_path(self, config: RunConfig) -> None:
        """resolver with db_path="" returns None from resolve()."""
        config.blast.pdb_aa_db = ""
        resolver = BLASTResolverPDBAA(config)
        
        result = resolver.resolve("MKWVTFISLLFLFSSAYS", as_similarity=False)
        
        assert result is None

    def test_preflight_missing_database_files(self, config: RunConfig) -> None:
        """resolver with db_path="/nonexistent/db" returns None."""
        config.blast.pdb_aa_db = "/nonexistent/db"
        resolver = BLASTResolverPDBAA(config)
        
        result = resolver.resolve("MKWVTFISLLFLFSSAYS", as_similarity=False)
        
        assert result is None

    def test_preflight_valid_db_path_still_runs(self, tmp_path: Path, config: RunConfig) -> None:
        """With valid-looking path, reaches subprocess (mock subprocess to avoid real blast)."""
        # Create a fake database directory with .pal file
        db_dir = tmp_path / "databases"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_file = db_dir / "testdb"
        pal_file = db_dir / "testdb.pal"
        pal_file.touch()  # Create empty .pal file
        
        config.blast.pdb_aa_db = str(db_file)
        resolver = BLASTResolverPDBAA(config)
        
        # Mock subprocess.run to simulate successful BLAST with no hits
        mock_result = MagicMock()
        mock_result.returncode = 0
        
        # Mock the JSON output file
        import json
        with patch('subprocess.run', return_value=mock_result):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = lambda s, *args: None
                mock_open.return_value.read.return_value = json.dumps({
                    "BlastOutput2": {
                        "report": {
                            "results": {
                                "search": {
                                    "query_len": 100,
                                    "hits": []
                                }
                            }
                        }
                    }
                })
                
                # Should not raise an exception, just return empty list
                result = resolver.resolve("MKWVTFISLLFLFSSAYS", as_similarity=False)
                assert result == []

    def test_blast_stderr_included_in_error_message(self, tmp_path: Path, config: RunConfig, caplog) -> None:
        """Verify BLAST stderr is captured and included in error message."""
        import logging
        caplog.set_level(logging.ERROR, logger="identifier")
        
        # Create fake DB files
        db_dir = tmp_path / "databases"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_file = db_dir / "testdb"
        pal_file = db_dir / "testdb.pal"
        pal_file.touch()  # Create .pal file for preflight check
        
        config.blast.pdb_aa_db = str(db_file)
        resolver = BLASTResolverPDBAA(config)
        
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "BLAST Database error: File not found"
        mock_result.stdout = ""
        
        with patch("subprocess.run", return_value=mock_result):
            result = resolver.resolve("MKWVTFISLLFLFSSAYS", as_similarity=False)
        
        # Exception propagates to resolve() which logs and returns None
        assert result is None
        # Check that the error log contains the stderr message
        assert "BLAST failed with return code 1" in caplog.text
        assert "BLAST Database error: File not found" in caplog.text


# =============================================================================
# Test Class: TestBlastBiologicalCorrectness
# =============================================================================

class TestBlastBiologicalCorrectness:
    """Tests verifying the math is biologically sound."""

    def test_identity_calculation_standard_formula(self, config: RunConfig) -> None:
        """identity_p = identity_count / align_len. For align_len=100, identity=95 -> 0.95."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["TEST"],
            identity=95,
            align_len=100,
            bits=150.0,
            evalue=1e-30
        )]
        json_data = make_blast_json(hits, query_len=100)
        
        results = resolver._process_blast_results(json_data)
        
        assert len(results) == 1
        assert results[0].identity_p == 0.95  # 95/100

    def test_coverage_calculation_standard_formula(self, config: RunConfig) -> None:
        """coverage_p = align_len / query_len. For query_len=200, align_len=150 -> 0.75."""
        resolver = BLASTResolverPDBAA(config)
        
        hits = [make_hit(
            accessions=["TEST"],
            identity=150,
            align_len=150,
            bits=150.0,
            evalue=1e-30
        )]
        json_data = make_blast_json(hits, query_len=200)
        
        results = resolver._process_blast_results(json_data)
        
        assert len(results) == 1
        assert results[0].coverage_p == 0.75  # 150/200

    def test_short_sequence_uses_blastp_short(self, config: RunConfig) -> None:
        """Sequence < 30 residues should trigger -task blastp-short."""
        resolver = BLASTResolverPDBAA(config)
        
        # Create fake DB files
        db_dir = Path(config.blast.pdb_aa_db).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        pal_file = Path(config.blast.pdb_aa_db + ".pal")
        pal_file.touch()
        
        # Short sequence (18 aa)
        short_seq = "MKWVTFISLLFLFSSAYS"
        assert len(short_seq) < 30
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = mock_result
            
            with patch('builtins.open', create=True) as mock_open:
                import json
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = lambda s, *args: None
                mock_open.return_value.read.return_value = json.dumps({
                    "BlastOutput2": {
                        "report": {
                            "results": {
                                "search": {
                                    "query_len": len(short_seq),
                                    "hits": []
                                }
                            }
                        }
                    }
                })
                
                try:
                    resolver._run_blast_local(short_seq, str(db_dir))
                except Exception:
                    pass  # We're just checking the call args
                
                # Verify -task blastp-short was passed
                call_args = mock_run.call_args[0][0]
                assert '-task' in call_args
                assert 'blastp-short' in call_args

    def test_long_sequence_no_short_task(self, config: RunConfig) -> None:
        """Sequence of 50 aa should NOT trigger -task blastp-short."""
        resolver = BLASTResolverPDBAA(config)
        
        # Create fake DB files
        db_dir = Path(config.blast.pdb_aa_db).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        pal_file = Path(config.blast.pdb_aa_db + ".pal")
        pal_file.touch()
        
        # Long sequence (50 aa)
        long_seq = "MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGEENFKALVL"
        assert len(long_seq) >= 30
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = mock_result
            
            with patch('builtins.open', create=True) as mock_open:
                import json
                mock_open.return_value.__enter__ = lambda s: s
                mock_open.return_value.__exit__ = lambda s, *args: None
                mock_open.return_value.read.return_value = json.dumps({
                    "BlastOutput2": {
                        "report": {
                            "results": {
                                "search": {
                                    "query_len": len(long_seq),
                                    "hits": []
                                }
                            }
                        }
                    }
                })
                
                try:
                    resolver._run_blast_local(long_seq, str(db_dir))
                except Exception:
                    pass  # We're just checking the call args
                
                # Verify -task blastp-short was NOT passed
                call_args = mock_run.call_args[0][0]
                assert '-task' not in call_args or 'blastp-short' not in call_args


# =============================================================================
# Test Class: TestBlastEndToEnd
# =============================================================================

class TestBlastEndToEnd:
    """End-to-end integration tests."""

    def test_identity_vs_similarity_same_hits_different_thresholds(self, config: RunConfig) -> None:
        """Same BLAST output processed with identity vs similarity filters produces different results."""
        resolver = BLASTResolverPDBAA(config)
        
        # Create hits that would pass similarity but fail identity
        hits = [
            # Good hit - passes both
            make_hit(["GOOD_HIT"], identity=100, align_len=100, bits=200.0, evalue=1e-100),
            # Similarity-only hit - fails identity thresholds
            make_hit(["SIMILAR_ONLY"], identity=50, align_len=80, bits=60.0, evalue=1e-10),
        ]
        json_data = make_blast_json(hits, query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            identity_result = resolver._run_blast_identity("SEQUENCE", "")
            similarity_result = resolver._run_blast_similarity("SEQUENCE", "")
        
        # Identity should only get the perfect hit
        assert identity_result == ["GOOD_HIT"]
        
        # Similarity should get both hits
        similarity_accessions = [r[0] for r in similarity_result]
        assert "GOOD_HIT" in similarity_accessions
        assert "SIMILAR_ONLY" in similarity_accessions

    def test_multiple_accessions_flattened(self, config: RunConfig) -> None:
        """Hit with accessions ["1A2B", "1A2C_A"] returns both in flat list."""
        resolver = BLASTResolverPDBAA(config)
        
        hit = {
            "description": [
                {"accession": "1A2B"},
                {"accession": "1A2C_A"}
            ],
            "hsps": [{
                "identity": 100,
                "align_len": 100,
                "bit_score": 200.0,
                "evalue": 1e-100
            }]
        }
        json_data = make_blast_json([hit], query_len=100)
        
        with patch.object(resolver, '_run_blast_local', return_value=json_data):
            identity_result = resolver._run_blast_identity("SEQUENCE", "")
            similarity_result = resolver._run_blast_similarity("SEQUENCE", "")
        
        # Both accessions should be in the flat list
        assert "1A2B" in identity_result
        assert "1A2C_A" in identity_result
        assert len(identity_result) == 2
        
        # Same for similarity
        similarity_accessions = [r[0] for r in similarity_result]
        assert "1A2B" in similarity_accessions
        assert "1A2C_A" in similarity_accessions
        assert len(similarity_result) == 2
