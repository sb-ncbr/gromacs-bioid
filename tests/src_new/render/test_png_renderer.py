"""Unit tests for src_new/render/png_renderer.py (pure core + stub-binary flow).

Stub pymol: a tiny shell script emulating `pymol -cq - (script on stdin)`.
The stub reads stdin and creates the PNG path found in the last `png` line,
letting us test planning, per-image timeouts, exit-code failures, missing output,
and the total budget WITHOUT a real PyMOL installation.
"""

from __future__ import annotations

import os
import stat
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

from src_new.render.png_renderer import (
    RenderConfig,
    RenderOutcome,
    RenderSpec,
    build_pymol_script,
    plan_renders,
    render_all,
    render_image,
    summarize,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _cfg(**kw):
    base = dict(pymol_bin="/bin/echo", total_budget_s=60, system_timeout_s=30,
                segment_timeout_s=10, reduced_style_at_atoms=1_000_000)
    base.update(kw)
    return RenderConfig(**base)


def _mk_run(root, mmcifs=("system.mmcif",)):
    """Create fake mmcif artifacts (content is irrelevant to the renderer)."""
    for name in mmcifs:
        (root / name).write_text("data_fake\n")


def _stub(tmp_path, body="""#!/bin/sh
# stub pymol: create png from last `png` line; honors SLEEP/EXITCODE env
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
# plan_renders (pure)
# ---------------------------------------------------------------------------

def test_plan_renders_orders_system_first(tmp_path):
    _mk_run(tmp_path, ("system.mmcif", "seg_1_A.mmcif", "seg_2_B.mmcif"))
    specs = plan_renders(tmp_path, ["seg_1_A", "seg_2_B"], 100, _cfg())
    assert [s.label for s in specs] == ["system", "seg_1_A", "seg_2_B"]


def test_plan_renders_full_style_below_threshold(tmp_path):
    _mk_run(tmp_path)
    specs = plan_renders(tmp_path, [], 999_999, _cfg())
    assert specs[0].style == "full"
    assert specs[0].timeout_s == 30


def test_plan_renders_reduced_style_at_threshold(tmp_path):
    _mk_run(tmp_path)
    specs = plan_renders(tmp_path, [], 1_000_000, _cfg())
    assert specs[0].style == "reduced"


def test_plan_renders_unknown_atom_count_stays_full(tmp_path):
    _mk_run(tmp_path)
    specs = plan_renders(tmp_path, [], None, _cfg())
    assert specs[0].style == "full"


def test_plan_renders_skips_missing_mmcifs(tmp_path):
    _mk_run(tmp_path, ("system.mmcif",))           # no seg mmcifs on disk
    specs = plan_renders(tmp_path, ["seg_1_A"], 100, _cfg())
    assert [s.label for s in specs] == ["system"]


def test_plan_renders_segments_use_seg_timeout_and_full_style(tmp_path):
    _mk_run(tmp_path, ("seg_1_A.mmcif",))
    specs = plan_renders(tmp_path, ["seg_1_A"], 100, _cfg())
    assert specs[0].timeout_s == 10
    assert specs[0].style == "full"


def test_plan_renders_paths_land_in_render_dir(tmp_path):
    _mk_run(tmp_path, ("system.mmcif", "seg_1_A.mmcif"))
    specs = plan_renders(tmp_path, ["seg_1_A"], 100, _cfg())
    assert specs[0].png_path == tmp_path / "render" / "system.png"
    assert specs[1].png_path == tmp_path / "render" / "segments" / "seg_1_A.png"


# ---------------------------------------------------------------------------
# build_pymol_script (pure)
# ---------------------------------------------------------------------------

def _spec(tmp_path, style="full", label="system"):
    mmcif = tmp_path / ("system.mmcif" if label == "system" else f"{label}.mmcif")
    png = tmp_path / "render" / (f"{label}.png" if label == "system" else f"segments/{label}.png")
    return RenderSpec(label=label, is_system=(label == "system"),
                      mmcif_path=mmcif, png_path=png, style=style, timeout_s=30)


def test_script_full_style_content(tmp_path):
    s = build_pymol_script(_spec(tmp_path), _cfg())
    assert "show cartoon, polymer.protein" in s
    assert "show sticks, ligands" in s
    assert "set opaque_background, 0" in s
    assert "png " in s and "ray=1" in s
    assert "width=1600, height=1200" in s


def test_script_reduced_style_omits_sticks_and_spheres(tmp_path):
    s = build_pymol_script(_spec(tmp_path, style="reduced"), _cfg())
    assert "show cartoon, polymer.protein" in s
    assert "show sticks" not in s
    assert "show spheres" not in s
    assert "width=1200, height=900" in s


def test_script_contains_input_and_output_paths(tmp_path):
    spec = _spec(tmp_path)
    s = build_pymol_script(spec, _cfg())
    assert str(spec.mmcif_path) in s
    assert str(spec.png_path) in s


# ---------------------------------------------------------------------------
# summarize (pure)
# ---------------------------------------------------------------------------

def test_summarize_counts():
    base = dict(png_path=None, style="full", ok=True, is_system=False, label="x")
    outcomes = [
        RenderOutcome(**{**base, "ok": True, "label": "a"}),
        RenderOutcome(**{**base, "ok": False, "error": "boom", "label": "b"}),
        RenderOutcome(**{**base, "ok": False, "skipped": True, "label": "c"}),
    ]
    stats = summarize(outcomes)
    assert stats == {"rendered": 1, "failed": 1, "skipped": 1, "total": 3}


# ---------------------------------------------------------------------------
# render_image / render_all (stub binary)
# ---------------------------------------------------------------------------

def test_render_image_success_creates_png(tmp_path):
    _mk_run(tmp_path)
    spec = plan_renders(tmp_path, [], 100, _cfg())[0]
    out = render_image(spec, _cfg(pymol_bin=_stub(tmp_path)))
    assert out.ok and out.png_path.is_file()


def test_render_image_reports_pymol_exit_failure(tmp_path):
    _mk_run(tmp_path)
    spec = plan_renders(tmp_path, [], 100, _cfg())[0]
    out = render_image(spec, _cfg(pymol_bin=_stub(tmp_path, body="#!/bin/sh\nexit 1\n")))
    assert not out.ok and "exited 1" in out.error


def test_render_image_reports_missing_binary(tmp_path):
    _mk_run(tmp_path)
    spec = plan_renders(tmp_path, [], 100, _cfg())[0]
    out = render_image(spec, _cfg(pymol_bin=None))
    assert not out.ok and out.error == "pymol_unavailable"


def test_render_image_timeout_kills(tmp_path):
    _mk_run(tmp_path)
    spec = plan_renders(tmp_path, [], 100, _cfg())[0]
    stub = _stub(tmp_path, body="#!/bin/sh\nsleep 30\n: > /dev/null\n")
    out = render_image(spec, _cfg(pymol_bin=stub), timeout_s=1)
    assert not out.ok and "timeout" in out.error


def test_render_all_budget_exhaustion_marks_skipped(tmp_path):
    _mk_run(tmp_path, ("system.mmcif", "seg_1.mmcif", "seg_2.mmcif"))
    specs = plan_renders(tmp_path, ["seg_1", "seg_2"], 100, _cfg())
    cfg = _cfg(pymol_bin=_stub(tmp_path, body="#!/bin/sh\nsleep 2\nexit 0\n"),
               total_budget_s=1, system_timeout_s=5)
    outcomes = render_all(specs, cfg)
    assert outcomes[0].ok is False                       # timed out
    assert all(o.skipped for o in outcomes[1:])          # budget consumed


# ---------------------------------------------------------------------------
# Env config (pure)
# ---------------------------------------------------------------------------

def test_from_env_defaults(monkeypatch):
    monkeypatch.delenv("BAT3_RENDER_PYMOL_BIN", raising=False)
    monkeypatch.setenv("PATH", os.defpath)
    cfg = RenderConfig.from_env()
    assert cfg.total_budget_s == 900
    assert cfg.reduced_style_at_atoms == 1_000_000


def test_from_env_overrides(monkeypatch):
    monkeypatch.setenv("BAT3_RENDER_PYMOL_BIN", "/opt/pymol")
    monkeypatch.setenv("BAT3_RENDER_TOTAL_BUDGET_S", "60")
    cfg = RenderConfig.from_env()
    assert cfg.pymol_bin == "/opt/pymol"
    assert cfg.total_budget_s == 60
