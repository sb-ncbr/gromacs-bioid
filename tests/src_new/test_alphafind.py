"""Tests for AlphaFind structure resolver."""

import unittest.mock as mock

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.alphafind import AlphaFindStructResolver


@pytest.fixture
def config():
    """Create a RunConfig with default alphafind settings."""
    return RunConfig()


@pytest.fixture
def resolver(config):
    """Create an AlphaFindStructResolver instance."""
    return AlphaFindStructResolver(config)


@pytest.fixture
def sample_pdb_content():
    """Sample CA-only PDB content for testing."""
    return """ATOM      1  CA  ALA A   1      10.000  10.000  10.000  1.00  0.00           C
ATOM      2  CA  GLY A   2      12.000  12.000  12.000  1.00  0.00           C
ATOM      3  CA  VAL A   3      14.000  14.000  14.000  1.00  0.00           C
TER
END
"""


class TestAlphaFindDirectResults:
    """Test case where POST returns results immediately."""

    def test_direct_results(self, config, sample_pdb_content):
        """Test when POST returns results directly without queuing."""
        post_response = {
            "results": [
                {"object_id": "A0A1", "aligned_percentage": 95.5}
            ],
            "digest": "d1",
            "search_time": 12.3
        }

        with mock.patch.object(AlphaFindStructResolver, '_alphafind_post', return_value=post_response):
            resolver = AlphaFindStructResolver(config)
            
            # Test similarity
            results = resolver._alphafind_similarity("/fake/path.pdb")
            assert len(results) == 1
            assert results[0] == ("A0A1", 95.5)
            
            # Test identity (should be empty since not 100%)
            identity = resolver._alphafind_identity("/fake/path.pdb")
            assert identity == []


class TestAlphaFindQueuedThenSuccess:
    """Test case where POST returns queue, then polling succeeds."""

    def test_queued_then_success(self, config, sample_pdb_content):
        """Test when POST returns queue position, then poll returns results."""
        post_response = {"queue_position": 2, "digest": "abc"}
        poll_response_1 = {"queue_position": 1, "digest": "abc"}
        poll_response_2 = {
            "results": [
                {"object_id": "A0A2", "aligned_percentage": 100.0}
            ],
            "digest": "abc"
        }

        # Track calls to verify poll was called
        poll_calls = []

        def mock_poll(digest):
            poll_calls.append(digest)
            if len(poll_calls) == 1:
                return poll_response_1
            return poll_response_2

        with mock.patch.object(AlphaFindStructResolver, '_alphafind_post', return_value=post_response):
            with mock.patch.object(AlphaFindStructResolver, '_alphafind_poll', side_effect=mock_poll):
                # Use very short poll interval for testing
                config.alphafind.poll_interval_s = 0
                config.alphafind.max_poll_attempts = 5
                
                resolver = AlphaFindStructResolver(config)
                
                # Test similarity
                results = resolver._alphafind_similarity("/fake/path.pdb")
                assert len(results) == 1
                assert results[0] == ("A0A2", 100.0)
                
                # Verify poll was called twice
                assert len(poll_calls) == 2
                assert all(d == "abc" for d in poll_calls)


class TestAlphaFindQueuedThenError:
    """Test case where POST returns queue, then polling returns error."""

    def test_queued_then_error(self, config, sample_pdb_content):
        """Test when POST returns queue, then poll returns error."""
        post_response = {"queue_position": 1, "digest": "xyz"}
        poll_error_response = {"code": "E", "message": "fail"}

        with mock.patch.object(AlphaFindStructResolver, '_alphafind_post', return_value=post_response):
            with mock.patch.object(AlphaFindStructResolver, '_alphafind_poll', return_value=poll_error_response):
                config.alphafind.poll_interval_s = 0
                config.alphafind.max_poll_attempts = 5
                
                resolver = AlphaFindStructResolver(config)
                
                # Test similarity - should return empty on error
                results = resolver._alphafind_similarity("/fake/path.pdb")
                assert results == []


class TestAlphaFindPostError:
    """Test case where POST returns error immediately."""

    def test_post_error(self, config, sample_pdb_content):
        """Test when POST returns error immediately."""
        post_response = {"code": "E", "message": "bad file"}

        with mock.patch.object(AlphaFindStructResolver, '_alphafind_post', return_value=post_response):
            resolver = AlphaFindStructResolver(config)
            
            # Test similarity - should return empty on error
            results = resolver._alphafind_similarity("/fake/path.pdb")
            assert results == []


class TestAlphaFindIdentityFilter:
    """Test identity filtering logic."""

    def test_identity_filter(self, config, sample_pdb_content):
        """Test that identity filter only returns 100% matches."""
        post_response = {
            "results": [
                {"object_id": "A0A1", "aligned_percentage": 100.0},
                {"object_id": "A0A2", "aligned_percentage": 95.0},
                {"object_id": "A0A3", "aligned_percentage": 80.0}
            ],
            "digest": "d1"
        }

        with mock.patch.object(AlphaFindStructResolver, '_alphafind_post', return_value=post_response):
            resolver = AlphaFindStructResolver(config)
            
            # Similarity returns all
            similarity = resolver._alphafind_similarity("/fake/path.pdb")
            assert len(similarity) == 3
            assert similarity[0] == ("A0A1", 100.0)
            assert similarity[1] == ("A0A2", 95.0)
            assert similarity[2] == ("A0A3", 80.0)
            
            # Identity returns only 100% match
            identity = resolver._alphafind_identity("/fake/path.pdb")
            assert len(identity) == 1
            assert identity[0] == "A0A1"


class TestAlphaFindNoResults:
    """Test case where search returns empty results."""

    def test_no_results(self, config, sample_pdb_content):
        """Test when POST returns empty results."""
        post_response = {
            "results": [],
            "digest": "x"
        }

        with mock.patch.object(AlphaFindStructResolver, '_alphafind_post', return_value=post_response):
            resolver = AlphaFindStructResolver(config)
            
            # Both similarity and identity should return empty
            similarity = resolver._alphafind_similarity("/fake/path.pdb")
            assert similarity == []
            
            identity = resolver._alphafind_identity("/fake/path.pdb")
            assert identity == []


class TestAlphaFindPollTimeout:
    """Test case where polling times out."""

    def test_poll_timeout(self, config, sample_pdb_content):
        """Test when polling exceeds max attempts."""
        post_response = {"queue_position": 3, "digest": "timeout_digest"}
        # Always return queued status
        poll_response = {"queue_position": 2, "digest": "timeout_digest"}

        poll_call_count = [0]  # Use list for mutable counter in closure

        def mock_poll(digest):
            poll_call_count[0] += 1
            return poll_response

        with mock.patch.object(AlphaFindStructResolver, '_alphafind_post', return_value=post_response):
            with mock.patch.object(AlphaFindStructResolver, '_alphafind_poll', side_effect=mock_poll):
                config.alphafind.poll_interval_s = 0  # No delay for testing
                config.alphafind.max_poll_attempts = 3
                
                resolver = AlphaFindStructResolver(config)
                
                # Should return empty after max polls
                results = resolver._alphafind_similarity("/fake/path.pdb")
                assert results == []
                
                # Verify correct number of poll attempts
                assert poll_call_count[0] == 3


class TestAlphaFindAcceptedSignatures:
    """Test accepted signature types."""

    def test_accepted_signatures_only_ca_only_pdb(self, config):
        """Test that resolver only accepts ca_only_pdb signatures."""
        resolver = AlphaFindStructResolver(config)
        
        assert resolver.accepted_signatures == ["ca_only_pdb"]
        assert "pdb_protein" not in resolver.accepted_signatures


class TestAlphaFindPollMethod:
    """Test the _alphafind_poll method directly."""

    def test_poll_uses_get_with_query_param(self, config):
        """Test that poll method uses GET with query parameter."""
        resolver = AlphaFindStructResolver(config)
        
        mock_response = mock.Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        
        with mock.patch.object(resolver._session, 'get', return_value=mock_response) as mock_get:
            resolver._alphafind_poll("test_digest")
            
            # Verify GET was called with correct URL
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            # URL should contain query=test_digest
            assert "query=test_digest" in call_args[0][0] or "query=test_digest" in call_args[1].get('url', '')


class TestAlphaFindResolveMethods:
    """Test the public resolve methods."""

    def test_resolve_similarity_returns_tuples(self, config):
        """Test _resolve_similarity returns list of tuples."""
        post_response = {
            "results": [
                {"object_id": "PDB1", "aligned_percentage": 90.0}
            ],
            "digest": "d1"
        }

        with mock.patch.object(AlphaFindStructResolver, '_alphafind_post', return_value=post_response):
            resolver = AlphaFindStructResolver(config)
            
            # Create a temp PDB file
            import tempfile
            import os
            
            fd, pdb_path = tempfile.mkstemp(suffix=".pdb")
            try:
                os.write(fd, b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n")
                os.close(fd)
                
                results = resolver._resolve_similarity("dummy_signature", "")
                assert isinstance(results, list)
                assert len(results) == 1
                assert isinstance(results[0], tuple)
                assert len(results[0]) == 2
                assert results[0][0] == "PDB1"
                assert results[0][1] == 90.0
            finally:
                if os.path.exists(pdb_path):
                    os.unlink(pdb_path)

    def test_resolve_identity_returns_strings(self, config):
        """Test _resolve_identity returns list of strings."""
        post_response = {
            "results": [
                {"object_id": "PDB1", "aligned_percentage": 100.0}
            ],
            "digest": "d1"
        }

        with mock.patch.object(AlphaFindStructResolver, '_alphafind_post', return_value=post_response):
            resolver = AlphaFindStructResolver(config)
            
            # Create a temp PDB file
            import tempfile
            import os
            
            fd, pdb_path = tempfile.mkstemp(suffix=".pdb")
            try:
                os.write(fd, b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n")
                os.close(fd)
                
                results = resolver._resolve_identity("dummy_signature", "")
                assert isinstance(results, list)
                assert len(results) == 1
                assert isinstance(results[0], str)
                assert results[0] == "PDB1"
            finally:
                if os.path.exists(pdb_path):
                    os.unlink(pdb_path)
