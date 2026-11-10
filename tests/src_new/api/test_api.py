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


class TestCapabilities:
    """BACKEND_GAPS contract §2 + G8: /api/v1/capabilities advertises
    landed additive features (the UI feature-detects) and the
    deployment-level typical-duration range."""

    def test_capabilities_defaults(self, client: TestClient,
                                   monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BAT3_TYPICAL_DURATION_MIN", raising=False)
        monkeypatch.delenv("BAT3_TYPICAL_DURATION_MAX", raising=False)
        response = client.get("/api/v1/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert body["api_version_marker"] >= 1
        additions = set(body["additions"])
        # every B1-wave feature must be advertised
        assert {"run_name_summary", "segment_meta_copies",
                "segment_progress", "results_csv",
                "capabilities"} <= additions
        assert body["typical_duration_minutes"] is None
        assert isinstance(body["code_version"], str) and body["code_version"]

    def test_capabilities_duration_env(self, client: TestClient,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_TYPICAL_DURATION_MIN", "30")
        monkeypatch.setenv("BAT3_TYPICAL_DURATION_MAX", "120")
        response = client.get("/api/v1/capabilities")
        assert response.status_code == 200
        assert response.json()["typical_duration_minutes"] == {
            "min": 30, "max": 120}

    def test_capabilities_duration_malformed_env(self, client: TestClient,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_TYPICAL_DURATION_MIN", "soon")
        monkeypatch.setenv("BAT3_TYPICAL_DURATION_MAX", "120")
        response = client.get("/api/v1/capabilities")
        assert response.status_code == 200
        assert response.json()["typical_duration_minutes"] is None


class TestRunNameSummary:
    """BACKEND_GAPS G1: run_name in the run summary (additive passthrough
    of pipeline.run_name, already persisted at creation)."""

    def _write_run(self, tmp_path: Path, run_id: str, pipeline: dict) -> None:
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "results.json").write_text(json.dumps({
            "pipeline": pipeline, "data": {},
        }))

    def test_run_name_in_summary(self, client: TestClient, tmp_path: Path,
                                 monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        self._write_run(tmp_path, "abc12", {
            "name": "BAT3", "status": "finished", "input_kind": "pdb",
            "run_name": "My first run", "started_at": "2026-10-21T08:10:51Z",
            "finished_at": "2026-10-21T08:23:45Z",
        })
        response = client.get("/runs/abc12")
        assert response.status_code == 200
        body = response.json()
        assert body["run_name"] == "My first run"
        # unnamed existing fields untouched (additive-only)
        assert body["run_id"] == "abc12"
        assert body["status"] == "finished"

    def test_run_name_null_for_older_runs(self, client: TestClient,
                                          tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
        """Old results.json payloads have no pipeline.run_name — the
        response must still be valid with run_name = null."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        self._write_run(tmp_path, "old9x", {
            "name": "BAT3", "status": "finished", "input_kind": "pdb",
        })
        response = client.get("/runs/old9x")
        assert response.status_code == 200
        assert response.json()["run_name"] is None


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


class TestSegmentProgress:
    """BACKEND_GAPS G2: additive `progress` block on /status, computed
    read-side from persisted state (segments the pipeline identified =
    signature-bearing universe segments ∪ single-copy fragments segments;
    searched iff identifiers/<seg> exists)."""

    def _write_run(self, tmp_path: Path, run_id: str, *, pipeline_status: str,
                   identify_status: str | None, with_fragments: bool,
                   identified_segs: list[str]) -> None:
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        tasks: dict = {}
        if identify_status is not None:
            tasks["generate_signatures"] = {"status": "success"}
            tasks["identify_molecules"] = {"status": identify_status}
        data_section: dict = {}
        if with_fragments:
            data_section = {
                "fragments": {
                    "unique": {}, "type_counts": {}, "total_count": 3,
                    "segments": [
                        {"segment": "A", "type": "protein", "copies": 1},
                        {"segment": "B", "type": "protein", "copies": 1},
                        # virtual/copies>1 — must NOT participate in progress
                        {"segment": "A__v1", "type": "water", "copies": 58},
                        # checking-only (no signatures) — must NOT participate
                        {"segment": "HOH", "type": "water", "copies": 1},
                    ],
                },
                "universe": {
                    "segment_list": ["A", "B", "A__v1", "HOH"],
                    "segments": {
                        "A": {"properties": {"is_protein": True}},
                        "B": {"properties": {"is_protein": True}},
                        "A__v1": {"properties": {}},
                        "HOH": {"properties": {}},
                    },
                },
                "signatures": {"A": {"generated": {"sequence|md5|64": {}}, "errors": []},
                               "B": {"generated": {"sequence|md5|64": {}}, "errors": []}},
                "identifiers": {seg: {"sequence|md5|64": {}} for seg in identified_segs},
            }
        (run_dir / "results.json").write_text(json.dumps({
            "pipeline": {"name": "BAT3", "status": pipeline_status,
                         "started_at": "2026-10-21T08:10:51Z"},
            "tasks": tasks,
            "data": data_section,
        }))

    def test_running_mid_identification(self, client: TestClient,
                                        tmp_path: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        self._write_run(tmp_path, "runA", pipeline_status="running",
                        identify_status="running", with_fragments=True,
                        identified_segs=["A"])
        response = client.get("/runs/runA/status")
        assert response.status_code == 200
        progress = response.json()["progress"]
        assert progress["molecules_done"] == 1
        assert progress["molecules_total"] == 2
        assert progress["per_segment"] == {"A": "searched", "B": "searching"}

    def test_pre_analysis_progress_absent(self, client: TestClient,
                                          tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
        """Before analysis there is no fragments block — progress is null."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        self._write_run(tmp_path, "runB", pipeline_status="running",
                        identify_status=None, with_fragments=False,
                        identified_segs=[])
        response = client.get("/runs/runB/status")
        assert response.status_code == 200
        assert response.json()["progress"] is None

    def test_terminal_run_all_searched(self, client: TestClient,
                                       tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        self._write_run(tmp_path, "runC", pipeline_status="success",
                        identify_status="success", with_fragments=True,
                        identified_segs=["A", "B"])
        response = client.get("/runs/runC/status")
        assert response.status_code == 200
        progress = response.json()["progress"]
        assert progress["molecules_done"] == 2
        assert progress["molecules_total"] == 2
        assert progress["per_segment"] == {"A": "searched", "B": "searched"}


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
                        # bughunt BH-014: the REAL persisted schema —
                        # status/error_code/error_message (the old fixture
                        # used success/error, which the loader never writes)
                        {"strategy": "auto_detect", "status": "failed",
                         "error_code": "load_exception",
                         "error_message": "No topology found"},
                        {"strategy": "pdb_direct", "status": "success"},
                    ],
                    "final_strategy": "pdb_direct",
                    "success": True,
                    "warnings": ["Missing hydrogens added"],
                    "failure_summary": None,
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
        assert validated.attempts[0].success is False
        assert validated.attempts[0].error == "No topology found"
        assert validated.attempts[0].error_code == "load_exception"
        assert validated.attempts[1].success is True
        assert len(validated.warnings) == 1


class TestLoadingFailureSummary:
    """bughunt BH-014: /loading surfaces the real failure reason."""

    def test_failed_run_reason_and_attempt_errors(self, client: TestClient,
                                                   tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        run_id = "f14"
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        results_data = {
            "pipeline": {"name": "BAT3", "status": "failed", "input_kind": "unknown"},
            "data": {
                "loading": {
                    "attempts": [
                        {"strategy": "gromacs_tpr", "status": "failed",
                         "error_code": "rejected_atoms",
                         "error_message": "atom count mismatch: topology has 36 atoms, traj.xtc has 30"},
                        {"strategy": "pdb_direct", "status": "failed",
                         "error_code": "load_exception",
                         "error_message": "UnicodeDecodeError: 'utf-8' codec"},
                    ],
                    "final_strategy": None,
                    "success": False,
                    "warnings": [],
                    "failure_summary": {
                        "reason": "atom_count_mismatch",
                        "message": "atom count mismatch: topology has 36 atoms, traj.xtc has 30",
                        "details": {"attempt_count": 2},
                    },
                }
            },
        }
        (run_dir / "results.json").write_text(json.dumps(results_data))
        response = client.get(f"/runs/{run_id}/loading")
        assert response.status_code == 200
        validated = LoadingInfoResponse.model_validate(response.json())
        assert validated.success is False
        assert validated.failure_summary["reason"] == "atom_count_mismatch"
        assert "36" in validated.attempts[0].error
        assert validated.attempts[0].error_code == "rejected_atoms"


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
                    # segments list mirrors the pipeline shape consumed by the
                    # endpoint (fragments/segments, then universe/segment_list)
                    "segments": [
                        {"segment": "PROA", "type": "protein",
                         "atoms_per_copy": 150, "residue_count": 50},
                    ],
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


class TestSegmentMetaCopies:
    """BACKEND_GAPS G3: copies + display_name + chain in segment_meta.

    display_name mirrors the UI's client-side baseName() exactly
    (ui/src/features/results/viewmodel/derive.ts): strip `seg_N_`
    prefix and `__vN` suffix, `_chain_X` suffix → "Chain X", else the
    (stripped) segment source name. Existing segment_meta keys
    (type/atom_count/residue_count) must be unchanged.
    """

    def _write_run(self, tmp_path: Path, run_id: str) -> None:
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        results_data = {
            "pipeline": {"name": "BAT3", "status": "finished"},
            "data": {
                "fragments": {
                    "unique": {},
                    "type_counts": {"protein": 1, "water": 1, "lipid": 1},
                    "total_count": 3,
                    "segments": [
                        {"segment": "seg_0_TOCL2", "type": "lipid",
                         "copies": 5, "atoms_per_copy": 130},
                        {"segment": "A__v1", "type": "water",
                         "copies": 58, "atoms_per_copy": 1},
                        {"segment": "Protein_chain_A", "type": "protein",
                         "copies": 1, "atoms_per_copy": 602},
                    ],
                },
                "universe": {
                    "segment_list": ["seg_0_TOCL2", "A__v1", "Protein_chain_A"],
                    "segments": {
                        "seg_0_TOCL2": {"properties": {
                            "atom_count_fragment": 130,
                            "atom_count_total": 650,
                            "residue_count": 5,
                        }},
                        "A__v1": {"properties": {
                            "atom_count_fragment": 1,
                            "atom_count_total": 58,
                            "residue_count": 58,
                        }},
                        "Protein_chain_A": {"properties": {
                            "is_protein": True,
                            "atom_count_fragment": 602,
                            "atom_count_total": 602,
                            "residue_count": 76,
                        }},
                    },
                },
            },
        }
        (run_dir / "results.json").write_text(json.dumps(results_data))

    def test_copies_display_name_and_chain(self, client: TestClient,
                                           tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        self._write_run(tmp_path, "g3mix")
        response = client.get("/runs/g3mix/molecules")
        assert response.status_code == 200
        meta = response.json()["segment_meta"]

        # lipid: seg_N_ prefix stripped, copies from fragments entry
        assert meta["seg_0_TOCL2"]["copies"] == 5
        assert meta["seg_0_TOCL2"]["display_name"] == "TOCL2"
        assert meta["seg_0_TOCL2"]["chain"] is None

        # water virtual sub-segment: __v1 stripped, many copies
        assert meta["A__v1"]["copies"] == 58
        assert meta["A__v1"]["display_name"] == "A"
        assert meta["A__v1"]["chain"] is None

        # chain-suffixed: human name + chain field
        assert meta["Protein_chain_A"]["copies"] == 1
        assert meta["Protein_chain_A"]["display_name"] == "Chain A"
        assert meta["Protein_chain_A"]["chain"] == "A"

        # additive-only: existing keys untouched
        assert meta["A__v1"]["type"] == "water"
        assert meta["A__v1"]["atom_count"] == 1
        assert meta["A__v1"]["residue_count"] == 58

    def test_copies_default_one_for_older_results(self, client: TestClient,
                                                  tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
        """Pre-v3.143 results with no fragments/segments copies field
        still yield copies=1 and a display_name derived from the name."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        run_dir = tmp_path / "g3old"
        run_dir.mkdir(parents=True)
        (run_dir / "results.json").write_text(json.dumps({
            "pipeline": {"name": "BAT3", "status": "finished"},
            "data": {
                "fragments": {"unique": {}, "type_counts": {},
                              "total_count": 0},
                "universe": {
                    "segment_list": ["L"],
                    "segments": {"L": {"properties": {
                        "atom_count_total": 21, "residue_count": 1}}},
                },
            },
        }))
        response = client.get("/runs/g3old/molecules")
        assert response.status_code == 200
        meta = response.json()["segment_meta"]
        assert meta["L"]["copies"] == 1
        assert meta["L"]["display_name"] == "L"
        assert meta["L"]["chain"] is None


class TestResultsCsv:
    """BACKEND_GAPS G6: GET /runs/{id}/download/results.csv — one clean
    row per leaderboard molecule; no internal segment ids or resolver
    churn in the values the user sees (segment key kept as first column
    for cross-referencing the UI rows)."""

    def _write_run(self, tmp_path: Path, run_id: str) -> None:
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        results_data = {
            "pipeline": {"name": "BAT3", "status": "finished"},
            "data": {
                "fragments": {
                    "unique": {}, "type_counts": {}, "total_count": 3,
                    "segments": [
                        {"segment": "Protein_chain_A", "type": "protein",
                         "copies": 1, "atoms_per_copy": 602},
                        {"segment": "seg_0_SOD", "type": "ion",
                         "copies": 12, "atoms_per_copy": 1},
                        {"segment": "L", "type": "small_molecule",
                         "copies": 1, "atoms_per_copy": 21},
                    ],
                },
                "universe": {
                    "segment_list": ["Protein_chain_A", "seg_0_SOD", "L"],
                    "segments": {
                        "Protein_chain_A": {"properties": {
                            "atom_count_fragment": 602, "residue_count": 76}},
                        "seg_0_SOD": {"properties": {
                            "atom_count_fragment": 1, "residue_count": 12}},
                        "L": {"properties": {
                            "atom_count_fragment": 21, "residue_count": 1}},
                    },
                },
                "signatures": {
                    "Protein_chain_A": {"generated": {"sequence|md5|64": {}}},
                    "seg_0_SOD": {"generated": {"atom|element|1": {}}},
                    "L": {"generated": {"graph|bliss|3|default|noncon|minfreq|rmol|neutral|cansmi|3": {}}},
                },
                "verification": {
                    "Protein_chain_A": {
                        "status": "complete",
                        "verified_hits": [
                            {"identifier": "1UBQ", "ident_type": "PDB_ID",
                             "database": "pdb", "final_confidence": 92.0,
                             "is_verified": True},
                            {"identifier": "3AUB", "ident_type": "PDB_ID",
                             "database": "pdb", "final_confidence": 61.0,
                             "is_verified": True},
                            {"identifier": "P0CG48", "ident_type": "UNIPROT_ID",
                             "database": "uniprot", "final_confidence": 88.0,
                             "is_verified": True},
                            {"identifier": "XYZ9", "ident_type": "PDB_ID",
                             "database": "pdb", "final_confidence": 30.0,
                             "is_verified": True},
                        ],
                    },
                    "seg_0_SOD": {
                        "status": "complete",
                        "verified_hits": [
                            {"identifier": "NA", "ident_type": "PUBCHEM_ATOM",
                             "database": "element", "final_confidence": None,
                             "is_verified": True},
                        ],
                    },
                    "L": {"status": "no_candidates", "verified_hits": []},
                },
            },
        }
        (run_dir / "results.json").write_text(json.dumps(results_data))

    def test_csv_columns_and_rows(self, client: TestClient, tmp_path: Path,
                                  monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        self._write_run(tmp_path, "csvr")
        response = client.get("/runs/csvr/download/results.csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        lines = response.text.replace("\r\n", "\n").strip().split("\n")
        assert lines[0] == (
            "Segment,Display Name,Kind,Copies,Atoms,Identified Name,"
            "Best Database,Best Identifier,Confidence,Confidence Label,"
            "Alternatives"
        )
        assert len(lines) == 4

        protein = lines[1].split(",")
        assert protein[0] == "Protein_chain_A"
        assert protein[1] == "Chain A"
        assert protein[2] == "protein"
        assert protein[3] == "1"
        assert protein[5] == ""              # identified name — lands with G5
        assert protein[6] == "pdb" and protein[7] == "1UBQ"
        assert protein[8] == "92.0" and protein[9] == "high"
        # top-3 alternatives excluding the best, db:id label form
        assert protein[10] == "pdb:3AUB uniprot:P0CG48 pdb:XYZ9"

        ion = lines[2].split(",")
        assert ion[0] == "seg_0_SOD" and ion[1] == "SOD"
        assert ion[3] == "12"
        assert ion[6] == "element" and ion[7] == "NA"
        assert ion[8] == "" and ion[9] == ""   # legacy null confidence

        unknown = lines[3].split(",")
        assert unknown[0] == "L" and unknown[1] == "L"
        assert unknown[6] == "" and unknown[7] == "" and unknown[8] == ""

        # no internal names in values
        body = "\n".join(lines)
        assert "__v" not in body

    def test_csv_404_for_missing_run(self, client: TestClient,
                                     tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        response = client.get("/runs/nope0/download/results.csv")
        assert response.status_code == 404


class TestUniqueMoleculesAdmission:
    """BACKEND_GAPS G7: unique_molecules — the store separates the
    representative instance's segment_ids (single segment) from the full
    group's segment_names (all identical segments, e.g. chains A–D in
    run 9d90d777). The API must surface BOTH; segment_ids keeps its
    documented instance semantics."""

    def test_segment_names_full_group_additive(self, client: TestClient,
                                               tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        run_dir = tmp_path / "g7run"
        run_dir.mkdir(parents=True)
        results_data = {
            "pipeline": {"name": "BAT3", "status": "finished"},
            "data": {
                "fragments": {
                    "unique": {
                        "type:protein|atoms:4260|residues:264": {
                            "segment_ids": ["seg_0_Protein_chain_A"],
                            "segment_names": ["seg_0_Protein_chain_A",
                                              "seg_1_Protein_chain_B",
                                              "seg_2_Protein_chain_C",
                                              "seg_3_Protein_chain_D"],
                            "molecule_type": "protein",
                            "atom_count": 4260,
                            "residue_count": 264,
                        },
                        "type:ion|atoms:1|residues:1|elements:Na=1": {
                            "segment_ids": ["seg_6_SOD"],
                            # older runs have no segment_names at all
                            "molecule_type": "ion",
                            "atom_count": 1,
                            "residue_count": 1,
                        },
                    },
                    "type_counts": {"protein": 1, "ion": 1},
                    "total_count": 2,
                    "segments": [
                        {"segment": "seg_0_Protein_chain_A", "type": "protein",
                         "copies": 1, "atoms_per_copy": 4260},
                        {"segment": "seg_6_SOD", "type": "ion",
                         "copies": 132, "atoms_per_copy": 1},
                    ],
                },
                "universe": {"segment_list": ["seg_0_Protein_chain_A",
                                              "seg_6_SOD"],
                             "segments": {}},
            },
        }
        (run_dir / "results.json").write_text(json.dumps(results_data))

        response = client.get("/runs/g7run/molecules")
        assert response.status_code == 200
        unique = response.json()["unique_molecules"]

        protein = unique["type:protein|atoms:4260|residues:264"]
        # the full group (chains A–D) is now visible
        assert protein["segment_names"] == [
            "seg_0_Protein_chain_A", "seg_1_Protein_chain_B",
            "seg_2_Protein_chain_C", "seg_3_Protein_chain_D"]
        # representative-instance semantics kept for legacy consumers
        assert protein["segment_ids"] == ["seg_0_Protein_chain_A"]

        ion = unique["type:ion|atoms:1|residues:1|elements:Na=1"]
        assert ion["segment_names"] == []  # older runs: key present, empty


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

    def test_render_segment_selectors_additive(self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """BACKEND_GAPS G9 (2/2): /render surfaces render/segment_selectors
        persisted at export (export-side commit) as typed per-segment
        selectors; absent on older runs (empty dict, additive)."""
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))

        # --- new run: selectors persisted -------------------------------
        run_dir = tmp_path / "g9run"
        run_dir.mkdir(parents=True)
        (run_dir / "results.json").write_text(json.dumps({
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {
                "render": {
                    "system_mmcif": "out/system.mmcif",
                    "segments": {"A": {"mmcif": "out/segments/A.mmcif"}},
                    "segment_selectors": {
                        "A": {"chains": ["A"],
                              "atom_index_ranges": [[0, 265]],
                              "atom_count": 265},
                        "A__v1": {"chains": ["A"],
                                  "atom_index_ranges": [[265, 266], [300, 358]],
                                  "atom_count": 59},
                    },
                },
            },
        }))

        response = client.get("/runs/g9run/render")
        assert response.status_code == 200
        body = response.json()
        sel = body["segment_selectors"]
        assert set(sel) == {"A", "A__v1"}
        # typed, passthrough from the persisted export record
        assert sel["A"] == {"chains": ["A"], "atom_index_ranges": [[0, 265]],
                            "atom_count": 265, "residue_ranges": None}
        # virtual segment: parent chain + exact (non-contiguous) ranges
        assert sel["A__v1"]["chains"] == ["A"]
        assert sel["A__v1"]["atom_index_ranges"] == [[265, 266], [300, 358]]
        assert sel["A__v1"]["atom_count"] == 59

        # --- older run without selectors: additive empty ------------------
        old_dir = tmp_path / "g9old"
        old_dir.mkdir(parents=True)
        (old_dir / "results.json").write_text(json.dumps({
            "pipeline": {"name": "BAT3", "status": "success"},
            "data": {"render": {"system_mmcif": "out/system.mmcif",
                                "segments": {}}},
        }))
        response = client.get("/runs/g9old/render")
        assert response.status_code == 200
        assert response.json()["segment_selectors"] == {}


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


class TestHitNameOrganism:
    """BACKEND_GAPS G5 (API side): additive name/organism on verified
    hits — passthrough of the fields the scorers thread onto the hit.

    Older runs have neither key (the scorers only fill them for
    macromolecular ident types, macromolecular payload permitting);
    the endpoint must then return null and the UI keeps its
    "PDB 1UBQ"-style fallback."""

    def _write_run(self, tmp_path: Path, run_id: str, hits: list) -> None:
        run_dir = tmp_path / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "results.json").write_text(json.dumps({
            "pipeline": {"name": "BAT3", "status": "finished"},
            "data": {"verification": {"PROA": {
                "status": "complete", "verified_hits": hits}}},
        }))

    def test_hit_name_organism_passthrough(self, client: TestClient,
                                           tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        self._write_run(tmp_path, "g5yes", [{
            "identifier": "1UBQ", "ident_type": "PDB_ID", "database": "pdb",
            "final_confidence": 92.0, "is_verified": True,
            "name": "Ubiquitin", "organism": "Homo sapiens",
        }])
        response = client.get("/runs/g5yes/verification")
        assert response.status_code == 200
        hit = response.json()["hits"][0]
        assert hit["name"] == "Ubiquitin"
        assert hit["organism"] == "Homo sapiens"
        assert hit["identifier"] == "1UBQ"  # existing fields untouched

    def test_hit_name_organism_null_on_older_runs(self, client: TestClient,
                                                  tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        self._write_run(tmp_path, "g5old", [{
            "identifier": "1UBQ", "ident_type": "PDB_ID", "database": "pdb",
            "final_confidence": 92.0, "is_verified": True,
        }])
        response = client.get("/runs/g5old/verification")
        assert response.status_code == 200
        hit = response.json()["hits"][0]
        assert hit["name"] is None
        assert hit["organism"] is None


class TestPostRunsEndpoint:
    """Tests for the POST /runs endpoint."""
    
class TestUploadSanitisation:
    """BH-013 (path traversal) and BH-017 (BOM) upload hardening."""

    PDB = b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n"

    def test_path_traversal_filename_stored_inside_input(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        response = client.post("/runs", files={"files": ("../x.pdb", self.PDB)})
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        saved = tmp_path / run_id / "input" / "x.pdb"
        assert saved.exists()
        # nothing escaped the run directory
        assert not (tmp_path / "x.pdb").exists()
        assert list((tmp_path / run_id / "input").iterdir()) == [saved]

    def test_absolute_path_filename_sanitised(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        response = client.post("/runs", files={"files": ("/etc/evil.pdb", self.PDB)})
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        assert (tmp_path / run_id / "input" / "evil.pdb").exists()

    def test_invalid_name_rejected_no_directory(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        response = client.post("/runs", files={"files": ("..", self.PDB)})
        assert response.status_code == 422
        assert list(tmp_path.iterdir()) == []  # no orphan run directory

    def test_duplicate_sanitised_names_rejected(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        response = client.post(
            "/runs",
            files=[("files", ("a.pdb", self.PDB)), ("files", ("../a.pdb", self.PDB))],
        )
        assert response.status_code == 422

    def test_bom_stripped_from_upload(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        response = client.post(
            "/runs", files={"files": ("bom.pdb", b"\xef\xbb\xbf" + self.PDB)})
        assert response.status_code == 200
        run_id = response.json()["run_id"]
        saved = tmp_path / run_id / "input" / "bom.pdb"
        assert saved.read_bytes() == self.PDB  # BOM gone

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

[identifiers]
blast_nt = no
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
        # The endpoint normalizes uploads through RunConfig (unknown sections
        # like [pipeline]/[loading] are dropped on round-trip; known keys must
        # survive), so byte-equality with the upload is not the contract.
        saved_text = saved_config.read_text()
        assert "blast_nt = False" in saved_text or "blast_nt = no" in saved_text
        assert "guess_missing_bonds = " in saved_text


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
