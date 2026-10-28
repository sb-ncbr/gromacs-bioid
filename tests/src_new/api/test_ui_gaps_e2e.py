"""Wave-B1 e2e grounding (BACKEND_GAPS G1/G2/G3/G6/G8 + capabilities).

Runs the REAL pipeline (stages 1-6: discover -> load -> repair -> unwrap
-> analyze universe -> generate signatures) on the committed
tests/fixtures/nucleic/cytc_full.pdb fixture into a temp run dir, points
the FastAPI test app at it, and asserts every B1 additive field from
actual pipeline output (not synthetic shapes):

  fragments/segments  -> A (protein), B (small_molecule), C/D (nucleic)
  signatures          -> all four segments (all single-copy)

Stage 7+ (identification/verification) needs database access and is out
of scope for a hermetic test; the one place the CSV shows hit values is
explicitly SEEDED with a verification record using the exact
d14-observed verified_hits shape (documented at the seed site).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new.api.main import app
from src_new.api.names import segment_display_name, strip_seg, chain_of

FIXTURE_PDB = (
    Path(__file__).resolve().parents[2] / "fixtures" / "nucleic" / "cytc_full.pdb"
)

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("MDAnalysis") is None
    or importlib.util.find_spec("rdkit") is None,
    reason="pipeline e2e needs MDAnalysis + rdkit",
)

# Stage 6 = Generate Signatures (stages 7+ need databases).
N_STAGES = 6


def _run_real_pipeline(runs_root: Path) -> Path:
    from src_new.pipeline_steps import build_load_and_export_tasks
    from src_new.executor.executor import PipelineExecutor
    from src_new.results.results_manager import ResultsManager

    run_dir = runs_root / "cytcE2E"
    run_dir.mkdir(parents=True)
    work = run_dir / "input"
    work.mkdir()
    shutil.copy(FIXTURE_PDB, work / "cytc.pdb")
    results_path = run_dir / "results.json"
    manager = ResultsManager(str(results_path), pipeline_name="ui-gaps-e2e")
    executor = PipelineExecutor(
        steps=build_load_and_export_tasks()[:N_STAGES],
        results_manager=manager,
        pipeline_name="ui-gaps-e2e",
    )
    executor.run(
        working_directory=work,
        output_directory=run_dir / "out",
        input_kind="pdb",
        input_files={"structure": work / "cytc.pdb"},
    )
    payload = json.loads(results_path.read_text())
    assert payload["pipeline"]["status"] == "success", (
        "real pipeline run must succeed; got "
        f"{payload['pipeline'].get('status')}: {payload.get('critical_errors')}"
    )
    return run_dir


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def runs_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("ui_e2e") / "runs"
    _run_real_pipeline(root)
    return root


@pytest.fixture(autouse=True)
def _point_at_real_runs(runs_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # NOTE: monkeypatch is function-scoped; runs_root is module-scoped —
    # re-point env per test. The mock_celery_task autouse fixture from
    # test_api.py is not imported here; no run creation happens in e2e.
    monkeypatch.setenv("BAT3_RUNS_DIR", str(runs_root))


class TestUiGapsE2E:
    """All assertions below read fields produced by the REAL pipeline."""

    def test_summary_run_name_passthrough(self, client: TestClient,
                                          runs_root: Path) -> None:
        """G1: seed pipeline.run_name into the REAL payload, then the
        summary must surface it (the creation endpoint is the only other
        writer of that field)."""
        results_path = runs_root / "cytcE2E" / "results.json"
        payload = json.loads(results_path.read_text())
        payload["pipeline"]["run_name"] = "cytc e2e label"
        results_path.write_text(json.dumps(payload))

        response = client.get("/runs/cytcE2E")
        assert response.status_code == 200
        assert response.json()["run_name"] == "cytc e2e label"
        assert response.json()["status"] == "success"

    def test_segment_meta_from_real_fragments(self, client: TestClient,
                                              runs_root: Path) -> None:
        """G3: real fragments/segments -> copies/display_name/chain
        populated, exact ground values for cytc_full (A protein,
        B ligand, C + D nucleic). Real value types (copies int)."""
        response = client.get("/runs/cytcE2E/molecules")
        assert response.status_code == 200
        body = response.json()
        meta = body["segment_meta"]
        assert set(body["segments"]) == {"A", "B", "C", "D"}

        assert meta["A"]["type"] == "protein"
        assert meta["B"]["type"] == "small_molecule"
        assert meta["C"]["type"] == "nucleic"
        assert meta["D"]["type"] == "nucleic"
        for seg in ("A", "B", "C", "D"):
            entry = meta[seg]
            assert isinstance(entry["copies"], int) and entry["copies"] >= 1
            assert entry["display_name"] == segment_display_name(seg)
            assert entry["chain"] == chain_of(strip_seg(seg))
            # additive-only on top of pre-existing keys
            assert "atom_count" in entry and "residue_count" in entry

    def test_status_progress_from_real_signatures(self, client: TestClient,
                                                  runs_root: Path) -> None:
        """G2: real signatures (all four segments) -> progress total 4;
        the identify stage never ran offline -> everything 'waiting',
        done 0. Terminal status consistency."""
        response = client.get("/runs/cytcE2E/status")
        assert response.status_code == 200
        progress = response.json()["progress"]
        assert progress is not None
        assert progress["molecules_total"] == 4
        assert progress["molecules_done"] == 0
        assert progress["per_segment"] == {
            "A": "waiting", "B": "waiting", "C": "waiting", "D": "waiting",
        }

    def test_results_csv_from_real_run(self, client: TestClient,
                                       runs_root: Path) -> None:
        """G6: one clean row per real segment; hit columns blank when
        nothing was searched. Then seed ONE verification record in the
        exact d14-observed verified_hits shape (stage 7+ needs a
        database and is out of scope hermetically) and assert the best
        hit + alternatives land in the row."""
        # --- unverified baseline (fully real) -----------------------------
        response = client.get("/runs/cytcE2E/download/results.csv")
        assert response.status_code == 200
        lines = response.text.replace("\r\n", "\n").strip().split("\n")
        assert lines[0] == (
            "Segment,Display Name,Kind,Copies,Atoms,Identified Name,"
            "Best Database,Best Identifier,Confidence,Confidence Label,"
            "Alternatives"
        )
        rows = {line.split(",")[0]: line.split(",") for line in lines[1:]}
        assert set(rows) == {"A", "B", "C", "D"}
        for seg, cols in rows.items():
            assert cols[1] == segment_display_name(seg)
            assert cols[5] == cols[6] == cols[7] == ""  # nothing searched
        assert rows["A"][2] == "protein" and rows["B"][2] == "small_molecule"

        # --- seeded verification (d14-observed verified_hits shape, see
        # bughunt_verify offline dumps / d14 run 2656); name/organism are
        # the G5 fields the scorers thread onto verified hits ----------
        results_path = runs_root / "cytcE2E" / "results.json"
        payload = json.loads(results_path.read_text())
        payload["data"]["verification"] = {
            "B": {
                "status": "complete",
                "verified_hits": [
                    {"identifier": "HEM", "ident_type": "PUBCHEM_NAME",
                     "database": "pdb_ligand", "final_confidence": 95.0,
                     "is_verified": True, "rejection_reason": None,
                     "name": "Heme"},
                    {"identifier": "5181", "ident_type": "PUBCHEM_LIGAND",
                     "database": "pubchem", "final_confidence": 62.5,
                     "is_verified": True, "rejection_reason": None},
                ],
            },
        }
        results_path.write_text(json.dumps(payload))

        response = client.get("/runs/cytcE2E/download/results.csv")
        rows = {line.split(",")[0]: line.split(",")
                for line in response.text.replace("\r\n", "\n").strip().split("\n")[1:]}
        best_row = rows["B"]
        assert best_row[5] == "Heme"  # G5 identified-name lands in the CSV
        assert best_row[6] == "pdb_ligand" and best_row[7] == "HEM"
        assert best_row[8] == "95.0" and best_row[9] == "high"
        assert best_row[10] == "pubchem:5181"
        assert rows["C"][6] == ""  # untouched segments stay blank

    def test_capabilities_e2e(self, client: TestClient) -> None:
        """G8 + capabilities: deployed endpoint advertises the landed B1
        wave and a non-empty code_version from the real app stack."""
        response = client.get("/api/v1/capabilities")
        assert response.status_code == 200
        body = response.json()
        assert body["api_version_marker"] >= 1
        assert {"run_name_summary", "segment_meta_copies",
                "segment_progress", "results_csv",
                "capabilities"} <= set(body["additions"])
        assert body["code_version"]
