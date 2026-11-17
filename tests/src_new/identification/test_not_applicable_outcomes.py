"""Resolvers that decline their input are skips, not failures (outcomes.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new.api.main import app
from src_new.identification.outcomes import is_not_applicable, user_warnings
from src_new.pipeline_steps import _record_resolver_errors

SKIP = "pdb_struct_nucleotide@sim (topology_less_pdb): na_mode_unsupported"
REAL = "blast_nr_protein (fasta_map_protein): BLAST timed out after 300s"


def test_reasons():
    assert is_not_applicable("na_mode_unsupported")
    assert is_not_applicable("mmcif_struct@sim (mmcif): no_polymer_payload")
    assert not is_not_applicable("HTTP Error 500: Internal Server Error")
    assert not is_not_applicable(None)


class _Results:
    def __init__(self):
        self.data = {}

    def get_data(self, path, default=None):
        return self.data.get(path, default)

    def set_data(self, path, value):
        self.data[path] = value


class _Context:
    def __init__(self):
        self.results = _Results()
        self.warnings = []

    def add_warning(self, code, message, details=None):
        self.warnings.append((code, message, details))


def test_new_runs_record_skips_as_data():
    ctx = _Context()
    _record_resolver_errors(ctx, "seg_0_A", [
        {"resolver": "pdb_struct_nucleotide@sim", "generator": "topology_less_pdb", "error": "na_mode_unsupported"},
        {"resolver": "blast_nr_protein", "generator": "fasta_map_protein", "error": "BLAST timed out after 300s"},
    ])
    _record_resolver_errors(ctx, "seg_0_A", [
        {"resolver": "mmcif_struct@sim", "generator": "mmcif", "error": "no_polymer_payload"}])
    assert [w[1] for w in ctx.warnings] == [REAL]
    skipped = ctx.results.data["identification/_meta/not_applicable/seg_0_A"]
    assert [s["reason"] for s in skipped] == ["na_mode_unsupported", "no_polymer_payload"]


@pytest.fixture
def old_run(tmp_path, monkeypatch):
    """A run recorded before 2026-11-17, with a skip among its warnings."""
    # The client starts first: its startup mounts /files on the runs dir of
    # the moment, for the whole session (as the other API tests do).
    client = TestClient(app).__enter__()
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr("src_new.api.routes.runs.run_pipeline_task.apply_async", lambda **k: None)
    d = tmp_path / "old-run"
    d.mkdir()
    warnings = [{"code": "identifier_resolver_failed", "message": m, "details": {"segment": "A"}}
                for m in (SKIP, REAL)] + [{"code": "pbc_unwrap_applied", "message": "ok", "details": {}}]
    (d / "results.json").write_text(json.dumps({
        "pipeline": {"name": "BAT3", "status": "success"}, "warnings": warnings, "data": {}}))
    assert len(user_warnings(warnings)) == 2
    yield client
    client.__exit__(None, None, None)


def test_api_hides_skips_of_older_runs(old_run):
    status = old_run.get("/api/v1/runs/old-run/status").json()
    assert [w["message"] for w in status["warnings"]] == [REAL, "ok"]
    assert status["warnings"][0]["docs_url"] == "/documentation/warnings/#identifier_resolver_failed"
    assert old_run.get("/api/v1/runs/old-run").json()["warning_count"] == 2
    failed = old_run.get("/api/v1/runs/old-run/identifiers").json()["failed_resolvers"]
    assert [f["resolver_name"] for f in failed] == ["blast_nr_protein"]
