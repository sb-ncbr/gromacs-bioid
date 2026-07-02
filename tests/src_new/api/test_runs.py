"""Tests for BAT3 runs API endpoints with new features."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new.api.main import app
from src_new.api.models import IdentifiersResponse, ResolverErrorItem


@pytest.fixture
def client() -> TestClient:
    """Create a TestClient for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def mock_celery_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock Celery task apply_async to avoid Redis connections during tests."""
    class MockAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id
        @property
        def status(self) -> str:
            return "PENDING"
        def ready(self) -> bool:
            return False
        def revoke(self, terminate: bool = False) -> None:
            pass
    
    def mock_apply_async(task_id: str = None, kwargs: dict = None) -> MockAsyncResult:
        return MockAsyncResult(task_id or "mock-task-id")
    
    monkeypatch.setattr(
        "src_new.api.routes.runs.run_pipeline_task.apply_async",
        mock_apply_async,
    )


class TestIdentifiersSegmentAware:
    """Tests for segment-aware identifier hits (API-17)."""
    
    def test_identifiers_hits_have_segment_field(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that each identifier hit includes the segment field."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-seg-aware"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        # Create results with multiple segments
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "identifiers": {
                    "PROA": {
                        "smiles": {
                            "pubchem_struct": {
                                "hit_type": "identity",
                                "hits": ["1234", "5678"],
                                "ident_type": "PUBCHEM_CID",
                            },
                            "attempted": ["pubchem_struct"],
                        }
                    },
                    "PRUB": {
                        "fasta": {
                            "pdb_seqres": {
                                "hit_type": "similarity",
                                "hits": [["9ABC", 0.95]],
                                "ident_type": "PDB_ID",
                            },
                            "attempted": ["pdb_seqres"],
                        }
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/identifiers")
        assert response.status_code == 200
        
        json_response = response.json()
        
        # Validate against Pydantic model
        validated = IdentifiersResponse.model_validate(json_response)
        
        # Check that all hits have segment field set correctly
        proa_hits = [h for h in validated.hits if h.segment == "PROA"]
        prub_hits = [h for h in validated.hits if h.segment == "PRUB"]
        
        assert len(proa_hits) == 2
        assert len(prub_hits) == 1
        
        # Verify segment field is set for each hit
        for hit in validated.hits:
            assert hit.segment is not None
            assert hit.segment in ["PROA", "PRUB"]
    
    def test_identifiers_with_segment_filter_has_segment_field(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that filtered identifiers still have segment field set."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-seg-filter"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "identifiers": {
                    "PROA": {
                        "smiles": {
                            "pubchem_struct": {
                                "hit_type": "identity",
                                "hits": ["1234"],
                                "ident_type": "PUBCHEM_CID",
                            },
                            "attempted": ["pubchem_struct"],
                        }
                    },
                    "PRUB": {
                        "smiles": {
                            "pubchem_struct": {
                                "hit_type": "identity",
                                "hits": ["5678"],
                                "ident_type": "PUBCHEM_CID",
                            },
                            "attempted": ["pubchem_struct"],
                        }
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        # Request only PROA
        response = client.get(f"/runs/{run_id}/identifiers?segment=PROA")
        assert response.status_code == 200
        
        json_response = response.json()
        validated = IdentifiersResponse.model_validate(json_response)
        
        # All hits should have segment = "PROA"
        assert validated.segment == "PROA"
        for hit in validated.hits:
            assert hit.segment == "PROA"


class TestResolverFailures:
    """Tests for resolver failure exposure (API-18)."""
    
    def test_failed_resolvers_parsed_from_warnings(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that identifier_resolver_failed warnings are parsed into failed_resolvers."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-failures"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "warnings": [
                {
                    "code": "identifier_resolver_failed",
                    "message": "pubchem_struct (smiles): Connection timeout",
                    "step_id": "task-identifiers",
                    "details": {},
                },
                {
                    "code": "identifier_resolver_failed",
                    "message": "pdb_seqres (fasta): Database not found",
                    "step_id": "task-identifiers",
                    "details": {},
                },
                {
                    "code": "OTHER_WARNING",
                    "message": "Some other warning",
                    "step_id": "task-other",
                    "details": {},
                }
            ],
            "data": {
                "identifiers": {
                    "PROA": {
                        "smiles": {
                            "pubchem_struct": {
                                "hit_type": "identity",
                                "hits": [],
                                "ident_type": "PUBCHEM_CID",
                            },
                            "attempted": ["pubchem_struct"],
                        }
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/identifiers")
        assert response.status_code == 200
        
        json_response = response.json()
        validated = IdentifiersResponse.model_validate(json_response)
        
        # Check failed_resolvers
        assert len(validated.failed_resolvers) == 2
        
        # Verify first failure
        fail1 = validated.failed_resolvers[0]
        assert fail1.resolver_name == "pubchem_struct"
        assert fail1.generator == "smiles"
        assert fail1.message == "Connection timeout"
        
        # Verify second failure
        fail2 = validated.failed_resolvers[1]
        assert fail2.resolver_name == "pdb_seqres"
        assert fail2.generator == "fasta"
        assert fail2.message == "Database not found"
    
    def test_failed_resolvers_deduplicated(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that duplicate resolver failures are deduplicated."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-dedup"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "warnings": [
                {
                    "code": "identifier_resolver_failed",
                    "message": "pubchem_struct (smiles): Connection timeout",
                    "step_id": "task-identifiers",
                    "details": {},
                },
                {
                    "code": "identifier_resolver_failed",
                    "message": "pubchem_struct (smiles): Connection timeout",
                    "step_id": "task-identifiers",
                    "details": {},
                }
            ],
            "data": {
                "identifiers": {
                    "PROA": {}
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/identifiers")
        assert response.status_code == 200
        
        json_response = response.json()
        validated = IdentifiersResponse.model_validate(json_response)
        
        # Should be deduplicated to one entry
        assert len(validated.failed_resolvers) == 1


class TestUploadSafeguards:
    """Tests for upload and config safeguards (API-19)."""
    
    def test_create_run_rejects_oversized_file(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that files larger than 128 MiB are rejected with HTTP 413."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        # Create a file larger than 128 MiB (we'll simulate with smaller size for testing)
        # For actual test, we create content just over the limit
        # But for speed, let's use a smaller threshold in the test
        # Actually, we need to test against the real constant
        # Let's create content that's definitely over 128 MiB
        # For testing purposes, we'll use 129 MB
        oversized_content = b"x" * (129 * 1024 * 1024)
        
        response = client.post(
            "/runs",
            files={"files": ("large_file.pdb", oversized_content)},
        )
        
        assert response.status_code == 413
        assert "exceeds 128 MiB limit" in response.json()["detail"]
    
    def test_create_run_rejects_malformed_config_json(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that malformed config JSON is rejected with HTTP 422."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        malformed_json = "{ invalid json content"
        
        response = client.post(
            "/runs",
            files={"files": ("test.pdb", b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n")},
            data={"config_json": malformed_json},
        )
        
        assert response.status_code == 422
        assert "Invalid config JSON" in response.json()["detail"]
    
    def test_create_run_rejects_unknown_config_section(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that unknown top-level config keys are rejected with HTTP 422."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        valid_json_with_unknown_key = json.dumps({
            "loader": {"guess_missing_elements": True},
            "unknown_section": {"some_key": "some_value"}
        })
        
        response = client.post(
            "/runs",
            files={"files": ("test.pdb", b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n")},
            data={"config_json": valid_json_with_unknown_key},
        )
        
        assert response.status_code == 422
        assert "Unknown config section" in response.json()["detail"]
        assert "unknown_section" in response.json()["detail"]
    
    def test_create_run_accepts_valid_config_json(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that valid config JSON is accepted."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        valid_json = json.dumps({
            "loader": {"guess_missing_elements": True},
            "executor": {"n_threads": 4}
        })
        
        response = client.post(
            "/runs",
            files={"files": ("test.pdb", b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n")},
            data={"config_json": valid_json},
        )
        
        assert response.status_code == 200
        json_response = response.json()
        assert "run_id" in json_response
        assert json_response["status"] == "queued"


class TestCORSConfiguration:
    """Tests for CORS configuration (API-20)."""
    
    def test_cors_allow_credentials_is_false(self) -> None:
        """Test that CORS middleware is configured with allow_credentials=False."""
        from src_new.api.main import app
        
        # Find the CORS middleware
        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                cors_middleware = middleware
                break
        
        assert cors_middleware is not None, "CORS middleware not found"
        
        # Check allow_credentials is False
        assert cors_middleware.kwargs.get("allow_credentials") is False, \
            "CORS allow_credentials should be False when allow_origins is '*'"
        
        # Verify allow_origins is still "*"
        assert cors_middleware.kwargs.get("allow_origins") == ["*"], \
            "CORS allow_origins should be ['*']"


class TestBlastMetadataExposure:
    """Tests for BLAST hit metadata exposure in API (BLAST-6)."""
    
    def test_identifiers_response_includes_metadata_fields(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that identifier hits include evalue, bit_score, identity_percent, coverage_percent."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-metadata"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        # Create results with hits_metadata
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "identifiers": {
                    "PROA": {
                        "fasta": {
                            "blast_pdb_protein": {
                                "hit_type": "similarity",
                                "hits": [["1A2B_A", 0.95]],
                                "ident_type": "PDB_ID",
                                "hits_metadata": {
                                    "1A2B_A": {
                                        "evalue": 1e-50,
                                        "bit_score": 150.0,
                                        "identity_p": 0.95,
                                        "coverage_p": 0.85
                                    }
                                }
                            },
                            "attempted": ["blast_pdb_protein"],
                        }
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/identifiers")
        assert response.status_code == 200
        
        json_response = response.json()
        
        # Validate response structure
        assert len(json_response["hits"]) == 1
        hit = json_response["hits"][0]
        
        # Check metadata fields are present
        assert "evalue" in hit
        assert "bit_score" in hit
        assert "identity_percent" in hit
        assert "coverage_percent" in hit
        
        # Check values are correctly transformed
        assert hit["evalue"] == 1e-50
        assert hit["bit_score"] == 150.0
        assert hit["identity_percent"] == 95.0  # 0.95 * 100
        assert hit["coverage_percent"] == 85.0  # 0.85 * 100
        
        # Validate against Pydantic model
        from src_new.api.models import IdentifiersResponse
        validated = IdentifiersResponse.model_validate(json_response)
        assert validated.hits[0].evalue == 1e-50
        assert validated.hits[0].bit_score == 150.0
        assert validated.hits[0].identity_percent == 95.0
        assert validated.hits[0].coverage_percent == 85.0
    
    def test_identifiers_without_metadata_still_works(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that identifiers without hits_metadata still work (backward compatibility)."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-no-metadata"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        # Create results WITHOUT hits_metadata
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "identifiers": {
                    "PROA": {
                        "smiles": {
                            "pubchem_struct": {
                                "hit_type": "identity",
                                "hits": ["1234"],
                                "ident_type": "PUBCHEM_CID",
                            },
                            "attempted": ["pubchem_struct"],
                        }
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/identifiers")
        assert response.status_code == 200
        
        json_response = response.json()
        assert len(json_response["hits"]) == 1
        hit = json_response["hits"][0]
        
        # Metadata fields should be None/missing for non-BLAST resolvers
        assert hit.get("evalue") is None
        assert hit.get("bit_score") is None
        assert hit.get("identity_percent") is None
        assert hit.get("coverage_percent") is None
    
    def test_identifiers_multiple_hits_with_metadata(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test metadata is correctly mapped for multiple hits."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-multi-metadata"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "identifiers": {
                    "PROA": {
                        "fasta": {
                            "blast_pdb_protein": {
                                "hit_type": "similarity",
                                "hits": [["1A2B_A", 0.95], ["3C4D_B", 0.75]],
                                "ident_type": "PDB_ID",
                                "hits_metadata": {
                                    "1A2B_A": {
                                        "evalue": 1e-50,
                                        "bit_score": 150.0,
                                        "identity_p": 0.95,
                                        "coverage_p": 0.85
                                    },
                                    "3C4D_B": {
                                        "evalue": 1e-20,
                                        "bit_score": 100.0,
                                        "identity_p": 0.75,
                                        "coverage_p": 0.60
                                    }
                                }
                            },
                            "attempted": ["blast_pdb_protein"],
                        }
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/identifiers")
        assert response.status_code == 200
        
        json_response = response.json()
        assert len(json_response["hits"]) == 2
        
        # Find hits by identifier
        hit1 = next(h for h in json_response["hits"] if h["identifier"] == "1A2B_A")
        hit2 = next(h for h in json_response["hits"] if h["identifier"] == "3C4D_B")
        
        # Check first hit metadata
        assert hit1["evalue"] == 1e-50
        assert hit1["bit_score"] == 150.0
        assert hit1["identity_percent"] == 95.0
        assert hit1["coverage_percent"] == 85.0
        
        # Check second hit metadata
        assert hit2["evalue"] == 1e-20
        assert hit2["bit_score"] == 100.0
        assert hit2["identity_percent"] == 75.0
        assert hit2["coverage_percent"] == 60.0



class TestHealthEndpoints:
    """Tests for health probe endpoints (API-22)."""
    
    def test_health_live_returns_200(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that GET /health/live returns 200."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        response = client.get("/health/live")
        
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}
    
    def test_health_ready_returns_200_when_ready(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that GET /health/ready returns 200 when runs dir exists and is writable."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        # Ensure env vars are set for Redis fallback
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        
        response = client.get("/health/ready")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
    
    def test_health_ready_returns_503_when_runs_dir_not_writable(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that GET /health/ready returns 503 when runs directory is not writable."""
        # Point to a non-existent path
        non_existent_path = tmp_path / "non_existent_dir"
        monkeypatch.setenv("BAT3_RUNS_DIR", str(non_existent_path))
        
        response = client.get("/health/ready")
        
        assert response.status_code == 503
        assert "Runs directory not writable" in response.json()["detail"]
    
    def test_health_check_exists(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that the original GET /health endpoint still works."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestRunCancellation:
    """Tests for run cancellation endpoint."""
    
    def test_cancel_running_run(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cancelling a running/queued run returns 200 and sets status to cancelled."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        # Create a run with "running" status
        run_id = "test-run-cancel"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {
                "name": "BAT3",
                "status": "running",
                "started_at": "2026-05-26T10:00:00Z",
            },
            "tasks": {},
            "warnings": [],
            "critical_errors": [],
            "events": [],
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        # Mock Celery AsyncResult to return STARTED status
        class MockAsyncResult:
            def __init__(self, task_id: str) -> None:
                self.id = task_id
                self._status = "STARTED"
            @property
            def status(self) -> str:
                return self._status
            def ready(self) -> bool:
                return False
            def revoke(self, terminate: bool = False) -> None:
                self._status = "REVOKED"
        
        def mock_async_result(task_id: str) -> MockAsyncResult:
            return MockAsyncResult(task_id)
        
        # Mock at the celery_app module level since cancel_run imports from there
        monkeypatch.setattr("src_new.celery_app.celery.AsyncResult", mock_async_result)
        
        # Cancel the run
        response = client.post(f"/runs/{run_id}/cancel")
        
        assert response.status_code == 200
        json_response = response.json()
        assert json_response["run_id"] == run_id
        assert json_response["status"] == "cancelled"
        
        # Verify results.json was updated
        with open(results_path, "r") as f:
            updated_data = json.load(f)
        assert updated_data["pipeline"]["status"] == "cancelled"
        assert "finished_at" in updated_data["pipeline"]
    
    def test_cancel_completed_run_returns_400(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cancelling a completed run returns 400."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-cancel-done"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {
                "name": "BAT3",
                "status": "success",
                "started_at": "2026-05-26T10:00:00Z",
                "finished_at": "2026-05-26T10:05:00Z",
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.post(f"/runs/{run_id}/cancel")
        
        assert response.status_code == 400
        assert "already in terminal state" in response.json()["detail"]
    
    def test_cancel_failed_run_returns_400(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cancelling a failed run returns 400."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-cancel-failed"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {
                "name": "BAT3",
                "status": "failed",
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.post(f"/runs/{run_id}/cancel")
        
        assert response.status_code == 400
    
    def test_cancel_already_cancelled_run_returns_400(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cancelling an already cancelled run returns 400."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-cancel-twice"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {
                "name": "BAT3",
                "status": "cancelled",
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.post(f"/runs/{run_id}/cancel")
        
        assert response.status_code == 400
    
    def test_cancel_nonexistent_run_returns_404(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test cancelling a non-existent run returns 404."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        response = client.post("/runs/nonexistent-run/cancel")
        
        assert response.status_code == 404


class TestStatusSinceParameter:
    """Tests for ?since= polling on status endpoint."""
    
    def test_status_without_since_returns_all(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test status endpoint without since returns all events/warnings/errors."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-since-all"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "updated_at": "2026-05-26T10:10:00Z",
            "pipeline": {
                "name": "BAT3",
                "status": "success",
                "started_at": "2026-05-26T10:00:00Z",
                "finished_at": "2026-05-26T10:05:00Z",
            },
            "tasks": {},
            "warnings": [
                {
                    "code": "WARN1",
                    "message": "First warning",
                    "recorded_at": "2026-05-26T10:01:00Z",
                },
                {
                    "code": "WARN2",
                    "message": "Second warning",
                    "recorded_at": "2026-05-26T10:03:00Z",
                },
            ],
            "critical_errors": [
                {
                    "code": "ERR1",
                    "message": "An error",
                    "recorded_at": "2026-05-26T10:02:00Z",
                },
            ],
            "events": [
                {"kind": "log", "timestamp": "2026-05-26T10:00:00Z", "message": "Start"},
                {"kind": "log", "timestamp": "2026-05-26T10:05:00Z", "message": "End"},
            ],
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/status")
        
        assert response.status_code == 200
        json_response = response.json()
        
        # Should have all items
        assert len(json_response["warnings"]) == 2
        assert len(json_response["critical_errors"]) == 1
        assert len(json_response["events"]) == 2
        assert json_response["updated_at"] == "2026-05-26T10:10:00Z"
    
    def test_status_with_since_filters_items(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test status endpoint with since filters events/warnings/errors correctly."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-since-filter"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "updated_at": "2026-05-26T10:10:00Z",
            "pipeline": {
                "name": "BAT3",
                "status": "success",
            },
            "tasks": {},
            "warnings": [
                {
                    "code": "WARN1",
                    "message": "First warning",
                    "recorded_at": "2026-05-26T10:01:00Z",
                },
                {
                    "code": "WARN2",
                    "message": "Second warning",
                    "recorded_at": "2026-05-26T10:05:00Z",
                },
            ],
            "critical_errors": [
                {
                    "code": "ERR1",
                    "message": "An error",
                    "recorded_at": "2026-05-26T10:02:00Z",
                },
                {
                    "code": "ERR2",
                    "message": "Later error",
                    "recorded_at": "2026-05-26T10:06:00Z",
                },
            ],
            "events": [
                {"kind": "log", "timestamp": "2026-05-26T10:00:00Z", "message": "Start"},
                {"kind": "log", "timestamp": "2026-05-26T10:03:00Z", "message": "Middle"},
                {"kind": "log", "timestamp": "2026-05-26T10:07:00Z", "message": "End"},
            ],
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        # Request since 10:04:00 - should only get items after this time
        response = client.get(f"/runs/{run_id}/status?since=2026-05-26T10:04:00Z")
        
        assert response.status_code == 200
        json_response = response.json()
        
        # Should only have items after 10:04:00
        assert len(json_response["warnings"]) == 1
        assert json_response["warnings"][0]["code"] == "WARN2"
        
        assert len(json_response["critical_errors"]) == 1
        assert json_response["critical_errors"][0]["code"] == "ERR2"
        
        assert len(json_response["events"]) == 1
        assert json_response["events"][0]["message"] == "End"
        
        # Pipeline and tasks should still be returned in full
        assert json_response["pipeline"]["status"] == "success"
    
    def test_status_with_since_includes_recorded_at(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that warnings/errors in status response include recorded_at."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-recorded-at"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {
                "name": "BAT3",
                "status": "success",
            },
            "tasks": {},
            "warnings": [
                {
                    "code": "WARN1",
                    "message": "A warning",
                    "recorded_at": "2026-05-26T10:01:00Z",
                },
            ],
            "critical_errors": [
                {
                    "code": "ERR1",
                    "message": "An error",
                    "recorded_at": "2026-05-26T10:02:00Z",
                },
            ],
            "events": [],
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/status")
        
        assert response.status_code == 200
        json_response = response.json()
        
        # Verify recorded_at is present
        assert len(json_response["warnings"]) == 1
        assert json_response["warnings"][0]["recorded_at"] == "2026-05-26T10:01:00Z"
        
        assert len(json_response["critical_errors"]) == 1
        assert json_response["critical_errors"][0]["recorded_at"] == "2026-05-26T10:02:00Z"
    
    def test_status_with_invalid_since_ignores_filter(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid since parameter is ignored and all items are returned."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-invalid-since"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {
                "name": "BAT3",
                "status": "success",
            },
            "tasks": {},
            "warnings": [
                {
                    "code": "WARN1",
                    "message": "A warning",
                    "recorded_at": "2026-05-26T10:01:00Z",
                },
            ],
            "critical_errors": [],
            "events": [],
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        # Invalid since format
        response = client.get(f"/runs/{run_id}/status?since=not-a-valid-timestamp")
        
        assert response.status_code == 200
        json_response = response.json()
        
        # Should still return all items
        assert len(json_response["warnings"]) == 1


