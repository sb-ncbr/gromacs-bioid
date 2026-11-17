"""Run list summaries (src_new/api/run_index.py): cached, re-read on change."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from src_new.api import run_index


def write(runs: Path, rid: str, status: str = "success", name: str | None = None) -> None:
    d = runs / rid
    d.mkdir(parents=True, exist_ok=True)
    (d / "results.json").write_text(json.dumps(
        {"created_at": "2026-11-17T10:00:00+00:00", "pipeline": {"status": status, "run_name": name}}))


def by_id(runs: Path) -> dict[str, dict]:
    return {s["run_id"]: s for s in run_index.summaries(runs)}


def test_summaries_follow_the_runs_directory(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    for i in range(40):  # more runs than I/O threads
        write(runs, f"run-{i}")
    write(runs, "busy", status="running")
    (runs / "_expired").mkdir()
    (runs / "no-results").mkdir()
    (runs / "broken").mkdir()
    (runs / "broken" / "results.json").write_text("{not json")
    assert set(by_id(runs)) == {f"run-{i}" for i in range(40)} | {"busy"}

    reads = []
    real = run_index._read
    monkeypatch.setattr(run_index, "_read", lambda n, p: reads.append(n) or real(n, p))
    write(runs, "busy", status="success", name="now with a longer name")
    shutil.rmtree(runs / "run-0")
    got = by_id(runs)
    assert got["busy"]["status"] == "success" and "run-0" not in got
    assert sorted(reads) == ["broken", "busy"]  # unchanged runs come from the cache
