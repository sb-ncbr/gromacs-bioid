"""Per-run tunable configuration and presets (src_new/config/presets.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new.config.loader import RunConfig
from src_new.config.presets import (
    PRESETS,
    TUNABLE,
    ConfigOverrideError,
    checked_overrides,
    overrides_from_ini,
    resolve_run_config,
    tunable_config,
)

PDB = b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n"


@pytest.fixture
def base() -> RunConfig:
    return RunConfig.from_default_ini()


@pytest.fixture
def client() -> TestClient:
    from src_new.api.main import app
    return TestClient(app)


@pytest.fixture(autouse=True)
def no_celery(monkeypatch):
    monkeypatch.setattr("src_new.api.routes.runs.run_pipeline_task.apply_async",
                        lambda *a, **k: None)


def test_every_preset_override_is_tunable_and_valid(base):
    assert [p["id"] for p in PRESETS] == ["balanced", "quick", "exact", "deep"]
    for preset in PRESETS:
        # checked_overrides raises on anything a user could not set either
        checked_overrides(preset["overrides"], base)


def test_exact_preset_turns_off_every_similarity_search(base):
    config = resolve_run_config("exact", None).to_dict()["identifiers"]
    sims = [k for k in TUNABLE["identifiers"] if k.endswith("_similarity")]
    assert sims and all(config[k] is False for k in sims)
    assert config["blast_pdb_protein"] is True


def test_quick_preset_skips_nr(base):
    config = resolve_run_config("quick", None)
    assert config.identifiers.blast_nr_protein is False
    assert config.verification.verify_top_n == 30


def test_tunable_config_has_no_plumbing(base):
    config = tunable_config(base)
    flat = {f"{s}.{k}" for s, fields in config.items() for k in fields}
    for forbidden in ("blast.blastp_exec", "blast.nr_aa_db", "foldseek.foldseek_exec",
                      "alphafind.url", "executor.identifiers_parallel", "timeouts.global_timeout_s",
                      "identifiers.sifts_db", "identifiers.deferred_resolvers",
                      "identifiers.overwrite_existing"):
        assert forbidden not in flat
    assert "identifiers.blast_nt" in flat
    assert "verification.verify_top_n" in flat


@pytest.mark.parametrize("overrides", [
    {"blast": {"blastp_exec": "/bin/sh"}},
    {"foldseek": {"foldseek_exec": "/tmp/x"}},
    {"alphafind": {"url": "http://169.254.169.254/"}},
    {"executor": {"n_threads": 500}},
    {"executor": {"identifiers_parallel": True}},
])
def test_plumbing_overrides_are_rejected(base, overrides):
    with pytest.raises(ConfigOverrideError, match="cannot be changed per run"):
        checked_overrides(overrides, base)


def test_unchanged_plumbing_is_dropped(base):
    full = base.to_dict()
    out = checked_overrides({"blast": dict(full["blast"]), "identifiers": {"blast_nt": False}}, base)
    assert out == {"identifiers": {"blast_nt": False}}


@pytest.mark.parametrize("overrides,message", [
    ({"verification": {"verify_top_n": 100000}}, "between"),
    ({"verification": {"verify_top_n": 10.5}}, "whole number"),
    ({"identifiers": {"blast_nt": "no"}}, "true or false"),
    ({"chembl": {"similarity_threshold": True}}, "number"),
    ({"nope": {"x": 1}}, "Unknown config section"),
    ({"loader": {"nope": 1}}, "Unknown config field"),
])
def test_bad_values_are_rejected(base, overrides, message):
    with pytest.raises(ConfigOverrideError, match=message):
        checked_overrides(overrides, base)


def test_ini_upload_is_read_on_top_of_the_defaults(base):
    assert overrides_from_ini("[identifiers]\nblast_nt = no\n", base) == {"identifiers": {"blast_nt": False}}
    with pytest.raises(ConfigOverrideError):
        overrides_from_ini("[blast]\nblastp_exec = /bin/sh\n", base)


def test_options_endpoint(client):
    body = client.get("/api/v1/runs/config/options").json()
    assert [p["id"] for p in body["presets"]] == ["balanced", "quick", "exact", "deep"]
    assert "blast" in body["config"] and "blastp_exec" not in body["config"]["blast"]


def _post(client, **data):
    return client.post("/runs", files={"files": ("test.pdb", PDB)}, data=data)


def test_submit_with_preset_and_override(client, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    r = _post(client, preset="quick", config_json=json.dumps({"verification": {"verify_top_n": 40}}))
    assert r.status_code == 200, r.text
    run_dir = tmp_path / r.json()["run_id"]
    saved = RunConfig.from_ini_path(run_dir / "config.ini")
    assert saved.identifiers.blast_nr_protein is False
    assert saved.verification.verify_top_n == 40
    assert json.loads((run_dir / "results.json").read_text())["pipeline"]["preset"] == "quick"


def test_submit_rejects_plumbing_before_writing(client, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    r = _post(client, config_json=json.dumps({"blast": {"blastp_exec": "/bin/sh"}}))
    assert r.status_code == 422
    r = client.post("/runs", files={"files": ("test.pdb", PDB),
                                    "config_file": ("config.ini", b"[blast]\nblastn_exec = /bin/sh\n")})
    assert r.status_code == 422
    r = _post(client, preset="turbo")
    assert r.status_code == 422 and "Unknown preset" in r.json()["detail"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("run_id", ["../../x", "a/b", "..", ".hidden"])
def test_submit_rejects_unsafe_run_id(client, tmp_path: Path, monkeypatch, run_id):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path / "runs"))
    r = client.post("/runs", params={"run_id": run_id}, files={"files": ("test.pdb", PDB)})
    assert r.status_code == 422
    assert not (tmp_path / "runs").exists() and not (tmp_path / "x").exists()
