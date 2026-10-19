"""Integration tests for the render_png pipeline task (v3.137).

Runs the REAL task handler (`src_new.pipeline_steps._render_png`) against a
fake-but-faithful StepContext: run directory with exported mmcifs, fake facade,
real ResultsManager. Verifies:

- paths recorded to data.render.system_png / render.segments.<seg>.png
- per-image failure / pymol absence / no-mmcif cases become WARNINGS (never fail)
- step summary reflects rendered/skipped/failed counts
"""

from __future__ import annotations

import json
import logging
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

from src_new.executor.task import StepContext, StepResult
from src_new.pipeline_steps import _render_png
from src_new.results.results_manager import ResultsManager


SEG = "seg_1_PROT"


class _FakeFacade:
    def __init__(self, segments):
        self._segments = segments

    def get_segments(self):
        return self._segments


def _mk_run(tmp_path, mmcifs=("system.mmcif", f"{SEG}.mmcif"),
            segments=(SEG,), n_atoms=100):
    """Build a minimal run dir + StepContext like the driver would."""
    run_dir = tmp_path
    for name in mmcifs:
        (run_dir / name).write_text("data_fake\n")
    results = ResultsManager(str(run_dir / "results.json"))
    if n_atoms is not None:
        results.set_data("simulation/n_atoms", n_atoms)
    logger = logging.getLogger("test")
    ctx = StepContext(results=results, state={"facade": _FakeFacade(list(segments))},
                      working_directory=run_dir, output_directory=run_dir,
                      logger=logger)
    ctx._current_step_id = "render_png"   # mirrors executor begin-task state
    return run_dir, results, ctx


def _stub(tmp_path, body="""#!/bin/sh
sleep ${SLEEP:-0}
out=$(grep -o '^png [^ ]*' "$2" 2>/dev/null | tail -1 | cut -d' ' -f2 | tr -d ',')
[ -n "$out" ] && : > "$out"
exit ${EXITCODE:-0}
"""):
    stub = tmp_path / "pymol_stub.sh"
    stub.write_text(body)
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(stub)


# ---------------------------------------------------------------------------

def test_render_png_records_paths_and_summary(tmp_path, monkeypatch):
    run_dir, results, ctx = _mk_run(tmp_path)
    monkeypatch.setenv("BAT3_RENDER_PYMOL_BIN", _stub(tmp_path))
    out = _render_png(ctx)
    assert isinstance(out, StepResult)
    assert out.summary["rendered"] == 2
    assert out.summary["failed"] == 0
    data = results._payload["data"]["render"]
    assert data["system_png"].endswith("render/system.png")
    assert data["segments"][SEG]["png"].endswith(f"render/segments/{SEG}.png")
    assert (run_dir / "render" / "system.png").is_file()
    assert (run_dir / "render" / "segments" / f"{SEG}.png").is_file()


def test_render_png_warns_on_missing_pymol(tmp_path, monkeypatch):
    run_dir, results, ctx = _mk_run(tmp_path)
    monkeypatch.delenv("BAT3_RENDER_PYMOL_BIN", raising=False)
    monkeypatch.setenv("PATH", "/nonexistent")                # force no pymol
    out = _render_png(ctx)
    assert out.summary["rendered"] == 0
    assert out.summary["reason"] == "pymol_unavailable"
    assert any(w["code"] == "render_pymol_unavailable"
               for w in results._payload["warnings"])


def test_render_png_warns_on_missing_mmcifs(tmp_path, monkeypatch):
    run_dir, results, ctx = _mk_run(tmp_path, mmcifs=())
    monkeypatch.setenv("BAT3_RENDER_PYMOL_BIN", _stub(tmp_path))
    out = _render_png(ctx)
    assert out.summary["rendered"] == 0
    assert out.summary["reason"] == "no_mmcifs"
    assert any(w["code"] == "render_no_mmcifs" for w in results._payload["warnings"])


def test_render_png_per_image_failure_becomes_warning(tmp_path, monkeypatch):
    run_dir, results, ctx = _mk_run(tmp_path)
    # stub that fails for segments (exit code 1), succeeds for system
    stub = tmp_path / "pymol_stub.sh"
    stub.write_text("""#!/bin/sh
out=$(grep -o '^png [^ ]*' "$2" 2>/dev/null | tail -1 | cut -d' ' -f2 | tr -d ',')
case "$out" in
  *segments*) exit 1 ;;
esac
[ -n "$out" ] && : > "$out"
exit 0
""")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("BAT3_RENDER_PYMOL_BIN", str(stub))
    out = _render_png(ctx)
    assert out.summary["rendered"] == 1                        # system only
    assert out.summary["failed"] == 1                          # seg failed
    assert any(w["code"] == "render_failed" for w in results._payload["warnings"])
    assert results._payload["data"]["render"]["system_png"].endswith("render/system.png")
    assert SEG not in results._payload["data"]["render"].get("segments", {})


def test_render_png_records_artifacts(tmp_path, monkeypatch):
    run_dir, results, ctx = _mk_run(tmp_path)
    monkeypatch.setenv("BAT3_RENDER_PYMOL_BIN", _stub(tmp_path))
    # _current_step_id must be set for add_artifact to write
    ctx._current_step_id = "export_results"
    ctx._reaper = None
    _render_png(ctx)
    assert any("render" in str(a.get("path", ""))
               for a in results._payload.get("artifacts", {}).values())


def test_render_png_reduced_style_for_huge_system(tmp_path, monkeypatch):
    run_dir, results, ctx = _mk_run(tmp_path, n_atoms=2_000_000)
    monkeypatch.setenv("BAT3_RENDER_PYMOL_BIN", _stub(tmp_path))
    out = _render_png(ctx)
    assert out.summary["rendered"] == 2
    # system.png rendered in reduced style (verifiable via script content elsewhere);
    # here we assert completion under the reduced-style path
    assert (run_dir / "render" / "system.png").is_file()


def test_render_png_no_facade_is_warning_and_success(tmp_path, monkeypatch):
    ctx = StepContext(results=ResultsManager(str(tmp_path / "results.json")),
                      state={}, working_directory=tmp_path,
                      output_directory=tmp_path, logger=logging.getLogger("t"))
    ctx._current_step_id = "render_png"
    monkeypatch.setenv("BAT3_RENDER_PYMOL_BIN", _stub(tmp_path))
    out = _render_png(ctx)
    assert out.summary["reason"] == "no_facade"
    assert any(w["code"] == "render_no_facade" for w in ctx.results._payload["warnings"])
