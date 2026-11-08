"""W3.2 item 2 (A6 corpus blocker): F14 export + render write amplification.

Production evidence (W3 package, F14 online run at b954adc33, 2952
segments): export_results 5675 s + render_png 2910 s — dominated by
SYNCHRONOUS per-segment results.json rewrites (export ~1.3 s/segment
from the very first segments; the render stage spent ~48 min AFTER
`render_budget_exhausted` fired, purely in the ok-outcome recording
loop: 1998 x (set_data + add_artifact) full-payload writes). The
render budget (900 s) was enforced for the PyMOL work itself but the
stage wall was not: the fleet kills runs at 3 h, so this is a corpus
blocker, not a performance nicety.

Fix contract pinned here:
1. export_results performs ALL its results writes (system + per
   segment + render paths) inside a deferred-saves window.
2. render_png performs its ok-outcome recording inside a
   deferred-saves window (the render budget then bounds the whole
   stage wall: PyMOL work + bounded flushes).
3. The default total render budget is 300 s (F14 export + render
   must land under 600 s; env override BAT3_RENDER_TOTAL_BUDGET_S is
   unchanged for fleets that want more UI fallback images).
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

from src_new.executor.task import StepContext
from src_new.pipeline_steps import _export_results, _render_png
from src_new.results.results_manager import ResultsManager


class _FakeFacade:
    def __init__(self, segments):
        self._segments = segments

    def get_segments(self):
        return self._segments


def _ctx(tmp_path, segments, n_atoms=100):
    results = ResultsManager(str(tmp_path / "results.json"))
    if n_atoms is not None:
        results.set_data("simulation/n_atoms", n_atoms)
    logger = __import__("logging").getLogger("test")
    ctx = StepContext(results=results,
                      state={"facade": _FakeFacade(list(segments))},
                      working_directory=tmp_path, output_directory=tmp_path,
                      logger=logger)
    ctx._current_step_id = "export_results"
    return ctx, results


def _counting_disk_writes(rm, monkeypatch):
    """Count actual results.json disk writes (atomic_write_json calls) —
    the write-amplification metric. _save() call counting would lie: the
    deferral throttle lives INSIDE _save."""
    import src_new.results.results_manager as rm_mod
    calls = {"n": 0}
    orig = rm_mod.atomic_write_json

    def counting(path, payload):
        calls["n"] += 1
        return orig(path, payload)

    monkeypatch.setattr(rm_mod, "atomic_write_json", counting)
    return calls


def test_export_writes_are_deferred(tmp_path, monkeypatch):
    """40 segments must not cost 2x40+ synchronous results.json rewrites."""
    import src_new.pipeline_steps as steps_mod

    N = 40
    segs = [f"seg_{i}" for i in range(N)]

    def stub_system(facade, path, results, **kwargs):
        path.write_text("data_fake\n")
        results.add_artifact("SYSTEM", path, kind="mmcif")
        results.set_data("exports/system_mmcif", str(path))

    def stub_segment(facade, seg, path, results):
        path.write_text("data_fake\n")
        results.add_artifact(seg, path, kind="mmcif")
        results.set_data(f"exports/segment_mmcif/{seg}", str(path))

    monkeypatch.setattr(steps_mod, "export_system_mmcif", stub_system)
    monkeypatch.setattr(steps_mod, "export_segment_mmcif", stub_segment)

    ctx, rm = _ctx(tmp_path, segs)
    saves = _counting_disk_writes(rm, monkeypatch)
    _export_results(ctx)

    # RED at the pre-fix SHA: ~3 writes per segment (artifact + export
    # path + render path) = 120+. GREEN: a deferred window throttles to
    # a couple of flushes regardless of segment count.
    assert saves["n"] <= 5, (
        f"export_results performed {saves['n']} synchronous full-payload "
        f"writes for {N} segments (write amplification, W3.2 item 2)")
    # content unchanged: every segment recorded
    for seg in segs:
        assert rm.get_data(f"exports/segment_mmcif/{seg}")
        assert rm.get_data(f"render/segments/{seg}/mmcif")
    assert rm.get_data("render/system_mmcif")


def test_render_recording_is_deferred(tmp_path, monkeypatch):
    """The ok-outcome recording loop must not rewrite results.json per
    image (F14 spent ~48 min there after the budget had fired)."""
    import src_new.render.png_renderer as renderer_mod
    from src_new.render.png_renderer import RenderOutcome

    N = 40
    segs = [f"seg_{i}" for i in range(N)]
    (tmp_path / "system.mmcif").write_text("data_fake\n")
    for s in segs:
        (tmp_path / f"{s}.mmcif").write_text("data_fake\n")

    pngs = []
    outcomes = []
    for s in segs:
        p = tmp_path / "render" / "segments" / f"{s}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("png\n")
        pngs.append(p)
        outcomes.append(RenderOutcome(s, False, p, "full", ok=True))
    syspng = tmp_path / "render" / "system.png"
    syspng.parent.mkdir(parents=True, exist_ok=True)
    syspng.write_text("png\n")
    outcomes.insert(0, RenderOutcome("system", True, syspng, "full", ok=True))

    monkeypatch.setattr(renderer_mod, "render_all", lambda specs, cfg: outcomes)
    monkeypatch.setenv("BAT3_RENDER_PYMOL_BIN", "/bin/true")

    ctx, rm = _ctx(tmp_path, segs)
    ctx._current_step_id = "render_png"
    saves = _counting_disk_writes(rm, monkeypatch)
    _render_png(ctx)

    assert saves["n"] <= 5, (
        f"render_png performed {saves['n']} synchronous full-payload writes "
        f"recording {N} ok outcomes (write amplification, W3.2 item 2)")
    for s in segs:
        assert rm.get_data(f"render/segments/{s}/png")
    assert rm.get_data("render/system_png")


def test_render_total_budget_default_is_300():
    """Contract for the F14 export+render < 600 s target: the default
    render budget must be 300 s (was 900 — F14 burned the whole budget
    on 1998 of 2952 lipid PNGs and still nearly hit the 3 h kill)."""
    from src_new.render.png_renderer import TOTAL_BUDGET_S_DEFAULT
    assert TOTAL_BUDGET_S_DEFAULT == 300
