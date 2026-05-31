"""Integration tests for BAT3 FastAPI API endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new.api.main import app
from src_new.api.models import (
    RunStatusResponse,
    LoadingInfoResponse,
    MoleculeSummaryResponse,
    RenderPathsResponse,
    SignaturesResponse,
    IdentifiersResponse,
    VerificationResponse,
)


@pytest.fixture
def client() -> TestClient:
    """Create a TestClient for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    """Create a temporary runs directory."""
    runs = tmp_path / "runs"
    runs.mkdir()
    return runs


@pytest.fixture(autouse=True)
def mock_celery_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock Celery task delay to avoid Redis connections during tests."""
    class MockAsyncResult:
        def __init__(self, task_id: str) -> None:
            self.id = task_id
        @property
        def status(self) -> str:
            return "PENDING"
        def ready(self) -> bool:
            return False
    
    def mock_delay(*args, **kwargs):
        return MockAsyncResult("mock-task-id")
    
    monkeypatch.setattr(
        "src_new.api.routes.runs.run_pipeline_task.delay",
        mock_delay,
    )


def create_fake_results(
    run_dir: Path,
    run_id: str,
    pipeline_data: dict | None = None,
    tasks_data: dict | None = None,
    warnings: list | None = None,
    errors: list | None = None,
    events: list | None = None,
    data_section: dict | None = None,
) -> Path:
    """Helper to create a fake results.json file."""
    run_path = run_dir / run_id
    run_path.mkdir(parents=True, exist_ok=True)
    
    results = {
        "pipeline": pipeline_data or {
            "name": "BAT3",
            "status": "success",
            "started_at": "2026-05-26T10:00:00Z",
            "finished_at": "2026-05-26T10:05:00Z",
            "input_kind": "pdb",
            "input_files": {"structure.pdb": "input/structure.pdb"},
            "metadata": {"version": "0.1.0"},
        },
        "tasks": tasks_data or {},
        "warnings": warnings or [],
        "critical_errors": errors or [],
        "events": events or [],
    }
    
    if data_section:
        results["data"] = data_section
    
    results_path = run_path / "results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    return results_path


class TestHealthEndpoint:
    """Tests for the /health endpoint."""
    
    def test_health(self, client: TestClient) -> None:
        """Test health check endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestRunsListEndpoint:
    """Tests for the GET /runs endpoint."""
    
    def test_get_runs_empty(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test listing runs when no runs exist."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        response = client.get("/runs")
        assert response.status_code == 200
        assert response.json()["runs"] == []


class TestRunNotFound:
    """Tests for 404 responses when run doesn't exist."""
    
    def test_get_run_not_found(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test accessing a non-existent run returns 404."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        response = client.get("/runs/nonexistent/status")
        assert response.status_code == 404


class TestRunStatusEndpoint:
    """Tests for the GET /runs/{run_id}/status endpoint."""
    
    def test_get_run_status(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting full run status with realistic payload."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-1"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        # Create realistic results.json
        results_data = {
            "pipeline": {
                "name": "BAT3",
                "status": "success",
                "started_at": "2026-05-26T10:00:00Z",
                "finished_at": "2026-05-26T10:05:00Z",
                "input_kind": "pdb",
                "input_files": {"structure.pdb": "input/structure.pdb"},
                "metadata": {"version": "0.1.0"},
            },
            "tasks": {
                "task-001": {
                    "task_id": "task-001",
                    "name": "Load Structure",
                    "status": "success",
                    "started_at": "2026-05-26T10:00:30Z",
                    "finished_at": "2026-05-26T10:01:00Z",
                    "summary": {"segments": ["PROA"], "residues": 150},
                    "artifacts": ["artifact-uuid-1"],
                },
                "task-002": {
                    "task_id": "task-002",
                    "name": "Identify Molecules",
                    "status": "success",
                    "started_at": "2026-05-26T10:01:00Z",
                    "finished_at": "2026-05-26T10:02:00Z",
                    "summary": {"molecules_found": 5},
                    "artifacts": ["artifact-uuid-2"],
                },
            },
            "warnings": [
                {
                    "code": "MISSING_ATOMS",
                    "message": "Some atoms were missing and reconstructed",
                    "step_id": "task-001",
                    "details": {"count": 3},
                }
            ],
            "critical_errors": [
                {
                    "code": "VALIDATION_ERROR",
                    "message": "Structure validation found issues",
                    "step_id": "task-001",
                    "details": {"severity": "medium"},
                    "critical": True,
                    "exception_type": None,
                }
            ],
            "events": [
                {
                    "kind": "log",
                    "timestamp": "2026-05-26T10:00:00Z",
                    "level": "INFO",
                    "message": "Pipeline started",
                    "task_id": None,
                },
                {
                    "kind": "step_start",
                    "timestamp": "2026-05-26T10:00:30Z",
                    "level": None,
                    "message": "Starting Load Structure task",
                    "task_id": "task-001",
                },
            ],
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/status")
        assert response.status_code == 200
        
        json_response = response.json()
        
        # Verify basic structure
        assert json_response["run_id"] == run_id
        assert json_response["pipeline"]["pipeline_name"] == "BAT3"
        assert len(json_response["tasks"]) == 2
        assert len(json_response["warnings"]) == 1
        assert len(json_response["critical_errors"]) == 1
        assert len(json_response["events"]) == 2
        
        # Validate against Pydantic model
        validated = RunStatusResponse.model_validate(json_response)
        assert validated.run_id == run_id
        assert validated.pipeline.pipeline_name == "BAT3"
        assert len(validated.tasks) == 2
        assert len(validated.warnings) == 1
        assert len(validated.critical_errors) == 1


class TestLoadingEndpoint:
    """Tests for the GET /runs/{run_id}/loading endpoint."""
    
    def test_get_run_loading(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting loading information."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-1"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {
                "name": "BAT3",
                "status": "success",
                "input_kind": "pdb",
            },
            "data": {
                "loading": {
                    "decision": {
                        "topology_files": ["structure.pdb"],
                        "strategy": "pdb_direct",
                    },
                    "attempts": [
                        {"strategy": "auto_detect", "success": False, "error": "No topology found"},
                        {"strategy": "pdb_direct", "success": True, "error": None},
                    ],
                    "final_strategy": "pdb_direct",
                    "success": True,
                    "warnings": ["Missing hydrogens added"],
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/loading")
        assert response.status_code == 200
        
        json_response = response.json()
        
        # Validate against Pydantic model
        validated = LoadingInfoResponse.model_validate(json_response)
        assert validated.run_id == run_id
        assert validated.input_kind == "pdb"
        assert validated.final_strategy == "pdb_direct"
        assert validated.success is True
        assert len(validated.attempts) == 2
        assert len(validated.warnings) == 1


class TestMoleculesEndpoint:
    """Tests for the GET /runs/{run_id}/molecules endpoint."""
    
    def test_get_run_molecules(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting molecule summary."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-1"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "fragments": {
                    "unique": {
                        "mol_001": {
                            "segment_ids": ["PROA"],
                            "molecule_type": "protein",
                            "atom_count": 150,
                            "residue_count": 50,
                            "smiles": "CC(=O)N",
                        },
                        "mol_002": {
                            "segment_ids": ["PROA"],
                            "molecule_type": "ligand",
                            "atom_count": 20,
                            "residue_count": 1,
                            "smiles": "CCO",
                        },
                    },
                    "type_counts": {"protein": 1, "ligand": 1},
                    "total_count": 2,
                    "by_segment": {
                        "PROA": {"count": 2, "molecules": ["mol_001", "mol_002"]},
                    },
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/molecules")
        assert response.status_code == 200
        
        json_response = response.json()
        
        # Validate against Pydantic model
        validated = MoleculeSummaryResponse.model_validate(json_response)
        assert validated.run_id == run_id
        assert len(validated.unique_molecules) == 2
        assert validated.type_counts == {"protein": 1, "ligand": 1}
        assert validated.total_fragment_count == 2
        assert validated.segments == ["PROA"]


class TestRenderEndpoint:
    """Tests for the GET /runs/{run_id}/render endpoint."""
    
    def test_get_run_render(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting render paths."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-1"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "render": {
                    "system_mmcif": "/path/to/system.cif",
                    "segments": {
                        "PROA": {
                            "mmcif": "/path/to/segments/PROA.cif",
                        },
                        "PRUB": {
                            "mmcif": "/path/to/segments/PRUB.cif",
                        },
                    },
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/render")
        assert response.status_code == 200
        
        json_response = response.json()
        
        # Validate against Pydantic model
        validated = RenderPathsResponse.model_validate(json_response)
        assert validated.run_id == run_id
        assert validated.system_mmcif == "/path/to/system.cif"
        assert len(validated.segments) == 2
        assert validated.segments["PROA"] == "/path/to/segments/PROA.cif"


class TestSignaturesEndpoint:
    """Tests for the GET /runs/{run_id}/signatures endpoint."""
    
    def test_get_run_signatures(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting signatures."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-1"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "signatures": {
                    "PROA": {
                        "generated": {
                            "smiles": "CCO",
                            "inchi": "InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3",
                        },
                        "attempted": ["smiles", "inchi"],
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/signatures")
        assert response.status_code == 200
        
        json_response = response.json()
        
        # Validate against Pydantic model
        validated = SignaturesResponse.model_validate(json_response)
        assert validated.run_id == run_id
        assert len(validated.signatures) == 2
        assert validated.attempted_generators["PROA"] == ["smiles", "inchi"]


class TestIdentifiersEndpoint:
    """Tests for the GET /runs/{run_id}/identifiers endpoint."""
    
    def test_get_run_identifiers(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting identifier hits."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-1"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        # Use nested structure: identifiers.{segment}.{generator}.{resolver}
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "identifiers": {
                    "PROA": {
                        "smiles": {
                            "pubchem_struct": {
                                "signature": "CCO",
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
        
        # Validate against Pydantic model
        validated = IdentifiersResponse.model_validate(json_response)
        assert validated.run_id == run_id
        assert validated.segment == "PROA"
        assert len(validated.hits) == 1
        assert validated.hits[0].identifier == "1234"
        assert validated.hits[0].ident_type == "PUBCHEM_CID"
        assert validated.hits[0].hit_type == "identity"
        assert validated.hits[0].resolver_name == "pubchem_struct"
        assert validated.hits[0].database_url == "https://pubchem.ncbi.nlm.nih.gov/compound/1234"
        assert "pubchem_struct" in validated.attempted_resolvers


class TestVerificationEndpoint:
    """Tests for the GET /runs/{run_id}/verification endpoint."""
    
    def test_get_run_verification(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting verification results."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-1"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "verification": {
                    "PROA": {
                        "verified_hits": [
                            {
                                "identifier": "1ABC",
                                "ident_type": "PDB_ID",
                                "database": "pdb",
                                "resolver_score": 100.0,
                                "similarity_score": None,
                                "annotation_quality_score": None,
                                "final_confidence": 80.0,
                                "is_verified": True,
                                "rejection_reason": None,
                                "supporting_evidence_count": 2,
                            }
                        ]
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        response = client.get(f"/runs/{run_id}/verification")
        assert response.status_code == 200
        
        json_response = response.json()
        
        # Validate against Pydantic model
        validated = VerificationResponse.model_validate(json_response)
        assert validated.run_id == run_id
        assert validated.segment == "PROA"
        assert len(validated.hits) == 1
        assert validated.hits[0].identifier == "1ABC"
        assert validated.hits[0].is_verified is True
        assert validated.hits[0].final_confidence == 80.0


class TestPostRunsEndpoint:
    """Tests for the POST /runs endpoint."""
    
    def test_post_runs(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test creating a new run by uploading a file."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        # Upload a PDB file
        response = client.post(
            "/runs",
            files={"files": ("test.pdb", b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n")},
        )
        
        assert response.status_code == 200
        json_response = response.json()
        
        assert "run_id" in json_response
        assert json_response["status"] == "queued"
        assert "message" in json_response
        assert "results_url" in json_response
        
        # Verify the file was saved
        run_id = json_response["run_id"]
        saved_file = tmp_path / run_id / "input" / "test.pdb"
        assert saved_file.exists()
        assert saved_file.read_bytes() == b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n"
    
    def test_post_runs_with_config(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test creating a new run with config file."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        config_content = """
[pipeline]
name = custom_pipeline
version = 1.0.0

[loading]
strategy = auto_detect
"""
        
        response = client.post(
            "/runs",
            files={
                "files": ("test.pdb", b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n"),
                "config_file": ("config.ini", config_content.encode()),
            },
        )
        
        assert response.status_code == 200
        json_response = response.json()
        
        assert "run_id" in json_response
        assert json_response["status"] == "queued"
        
        # Verify both files were saved
        run_id = json_response["run_id"]
        saved_pdb = tmp_path / run_id / "input" / "test.pdb"
        saved_config = tmp_path / run_id / "config.ini"
        
        assert saved_pdb.exists()
        assert saved_config.exists()
        assert saved_config.read_text() == config_content


class TestStaticFilesEndpoint:
    """Tests for the /files static file serving endpoint."""
    
    def test_static_file_serving(self, client: TestClient) -> None:
        """Test that static files can be served from the runs directory."""
        import os
        from src_new.api.routes.runs import get_runs_dir
        
        # Use the actual runs directory
        runs_dir = get_runs_dir()
        
        # Create a run directory with a test file
        run_id = "test-run-static"
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Create a test file
            test_file = run_dir / "test.txt"
            test_file.write_text("Hello from static files!")
            
            # Access via static mount
            response = client.get(f"/files/{run_id}/test.txt")
            assert response.status_code == 200
            assert response.text == "Hello from static files!"
        finally:
            # Cleanup
            import shutil
            if run_dir.exists():
                shutil.rmtree(run_dir)
    
    def test_static_file_not_found(self, client: TestClient) -> None:
        """Test that non-existent files return 404."""
        import os
        from src_new.api.routes.runs import get_runs_dir
        
        runs_dir = get_runs_dir()
        
        run_id = "test-run-notfound"
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Try to access non-existent file
            response = client.get(f"/files/{run_id}/nonexistent.txt")
            assert response.status_code == 404
        finally:
            # Cleanup
            import shutil
            if run_dir.exists():
                shutil.rmtree(run_dir)


class TestSegmentFiltering:
    """Tests for segment query parameter filtering."""
    
    def test_signatures_with_segment_filter(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test signatures endpoint with segment filter returns only requested segment."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-seg"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        # Create results with multiple segments
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "signatures": {
                    "PROA": {
                        "generated": {"smiles": "CCO_PROA"},
                        "attempted": ["smiles"],
                    },
                    "PRUB": {
                        "generated": {"smiles": "CCO_PRUB", "inchi": "InChI_PRUB"},
                        "attempted": ["smiles", "inchi"],
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        # Request only PROA
        response = client.get(f"/runs/{run_id}/signatures?segment=PROA")
        assert response.status_code == 200
        json_response = response.json()
        
        # Should only have PROA signatures
        assert len(json_response["signatures"]) == 1
        assert json_response["signatures"][0]["segment"] == "PROA"
        assert json_response["signatures"][0]["signature"] == "CCO_PROA"
        assert "PROA" in json_response["attempted_generators"]
        assert "PRUB" not in json_response["attempted_generators"]
    
    def test_identifiers_with_segment_filter(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test identifiers endpoint with segment filter returns only requested segment."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-seg"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        # Create results with multiple segments using nested structure
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "identifiers": {
                    "PROA": {
                        "smiles": {
                            "pubchem_struct": {
                                "signature": "CCO",
                                "hit_type": "identity",
                                "hits": ["1234"],
                                "ident_type": "PUBCHEM_CID",
                            },
                            "attempted": ["pubchem_struct"],
                        }
                    },
                    "PRUB": {
                        "fasta": {
                            "pdb_seqres": {
                                "signature": "MKTVRQ",
                                "hit_type": "similarity",
                                "hits": [["5XYZ", 0.95]],
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
        
        # Request only PROA
        response = client.get(f"/runs/{run_id}/identifiers?segment=PROA")
        assert response.status_code == 200
        json_response = response.json()
        
        # Should only have PROA identifiers
        assert json_response["segment"] == "PROA"
        assert len(json_response["hits"]) == 1
        assert json_response["hits"][0]["identifier"] == "1234"
        assert json_response["hits"][0]["ident_type"] == "PUBCHEM_CID"
    
    def test_verification_with_segment_filter(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test verification endpoint with segment filter returns only requested segment."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-seg"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        # Create results with multiple segments
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "verification": {
                    "PROA": {
                        "verified_hits": [
                            {
                                "identifier": "1ABC",
                                "ident_type": "PDB_ID",
                                "database": "pdb",
                                "resolver_score": 100.0,
                                "similarity_score": None,
                                "annotation_quality_score": None,
                                "final_confidence": 80.0,
                                "is_verified": True,
                                "rejection_reason": None,
                                "supporting_evidence_count": 2,
                            }
                        ]
                    },
                    "PRUB": {
                        "verified_hits": [
                            {
                                "identifier": "2XYZ",
                                "ident_type": "PDB_ID",
                                "database": "pdb",
                                "resolver_score": 95.0,
                                "similarity_score": None,
                                "annotation_quality_score": None,
                                "final_confidence": 75.0,
                                "is_verified": True,
                                "rejection_reason": None,
                                "supporting_evidence_count": 1,
                            }
                        ]
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        # Request only PROA
        response = client.get(f"/runs/{run_id}/verification?segment=PROA")
        assert response.status_code == 200
        json_response = response.json()
        
        # Should only have PROA verification hits
        assert json_response["segment"] == "PROA"
        assert len(json_response["hits"]) == 1
        assert json_response["hits"][0]["identifier"] == "1ABC"
        assert json_response["hits"][0]["final_confidence"] == 80.0
    
    def test_signatures_nonexistent_segment(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test signatures endpoint with non-existent segment returns empty results."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        
        run_id = "test-run-seg"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        
        # Create results with one segment
        results_data = {
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "signatures": {
                    "PROA": {
                        "generated": {"smiles": "CCO_PROA"},
                        "attempted": ["smiles"],
                    }
                }
            },
        }
        
        results_path = run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        
        # Request non-existent segment
        response = client.get(f"/runs/{run_id}/signatures?segment=NONEXISTENT")
        assert response.status_code == 200
        json_response = response.json()
        
        # Should have no signatures
        assert len(json_response["signatures"]) == 0
        assert json_response["attempted_generators"] == {}

class TestConfigEndpoints:
    """Tests for the GET /runs/config/default and /runs/config/parallel-default endpoints."""
    
    def test_get_config_default_returns_json(self, client: TestClient) -> None:
        """Test that /runs/config/default returns valid JSON with status 200."""
        response = client.get("/runs/config/default")
        assert response.status_code == 200
        
        # Verify it's valid JSON
        json_response = response.json()
        assert isinstance(json_response, dict)
        
        # Verify expected sections exist
        assert "executor" in json_response
        assert "loader" in json_response
        assert "signatures" in json_response
        assert "identifiers" in json_response
        assert "verification" in json_response
        assert "timeouts" in json_response
    
    def test_get_config_parallel_default(self, client: TestClient) -> None:
        """Test that /runs/config/parallel-default returns config with parallelism enabled."""
        response = client.get("/runs/config/parallel-default")
        assert response.status_code == 200
        
        json_response = response.json()
        assert isinstance(json_response, dict)
        
        # Verify parallelism flags are enabled
        assert json_response.get("executor", {}).get("signatures_parallel") is True
        assert json_response.get("executor", {}).get("identifiers_parallel") is True
        assert json_response.get("executor", {}).get("verification_parallel") is True
    
    def test_get_config_default_structure(self, client: TestClient) -> None:
        """Test that /runs/config/default returns expected structure."""
        response = client.get("/runs/config/default")
        assert response.status_code == 200
        
        json_response = response.json()
        
        # Verify executor section has expected fields
        executor = json_response.get("executor", {})
        assert "n_threads" in executor
        assert "tps" in executor
        assert "emit_queue_stats" in executor
        assert "signatures_parallel" in executor
        assert "identifiers_parallel" in executor
        assert "verification_parallel" in executor
        
        # Verify default parallelism is False
        assert executor.get("signatures_parallel") is False
        assert executor.get("identifiers_parallel") is False
        assert executor.get("verification_parallel") is False
