"""Headless PyMOL PNG renderers for the render_png pipeline task (v3.137).

Why this exists: MolstarViewer (UI) falls back to /files/<run>/render/system.png
(and, post-v3.137, render/segments/<seg>.png) whenever the interactive Mol*
view times out or the system is too large. Nobody generated those PNGs before
this module. Design rules (user ruling 2026-10-19):

- Renders FROM the exported mmcifs (system.mmcif / <seg>.mmcif at run root)
  so the static image depicts exactly what Mol* would show.
- Style mirrors the Mol* MVS default: cartoon proteins, ball-and-stick-ish
  non-polymer (sticks + small spheres for ions), chain colouring, transparent
  background. HUGE systems (>= REDUCED_STYLE_ATOMS) degrade to a cheaper
  style (cartoon only, no spheres/sticks/hydrogens, lower resolution) so the
  system image still renders in bounded time; per-segment images always use
  full style because segments are small.
- Everything is budget-bounded (per-image + total task budget, wall seconds)
  and failure-isolated: the caller turns individual failures into pipeline
  warnings; this module never raises for a single image failure.

Pure core (unit-testable, no IO): RenderConfig, RenderSpec, plan_renders(),
build_pymol_script(), summarize(). IO shell: render_image(), render_all().

PyMOL specifics: batch mode `pymol -cq script.pml`, software ray tracing
(`png ..., ray=1`) — the ONLY headless-safe path (no X/GL). Transparency via
opaque_background=0. Binary resolved via env BAT3_RENDER_PYMOL_BIN or PATH.
All knobs are environment-configurable but documented here (no hidden toggles,
per the F-21 dead-toggle lesson).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration (pure data)
# ---------------------------------------------------------------------------

#: Total-atom threshold at/above which system renders switch to reduced style.
REDUCED_STYLE_ATOMS_DEFAULT = 1_000_000
#: Task-level and per-image wall-clock budgets (seconds).
TOTAL_BUDGET_S_DEFAULT = 900
SYSTEM_TIMEOUT_S_DEFAULT = 300
SEGMENT_TIMEOUT_S_DEFAULT = 120
#: Full/reduced ray-traced resolution (width, height).
RESOLUTION_FULL = (1600, 1200)
RESOLUTION_REDUCED = (1200, 900)
RENDER_DIRNAME = "render"
SEGMENTS_DIRNAME = "segments"


@dataclass(frozen=True)
class RenderConfig:
    pymol_bin: str | None
    total_budget_s: int = TOTAL_BUDGET_S_DEFAULT
    system_timeout_s: int = SYSTEM_TIMEOUT_S_DEFAULT
    segment_timeout_s: int = SEGMENT_TIMEOUT_S_DEFAULT
    reduced_style_at_atoms: int = REDUCED_STYLE_ATOMS_DEFAULT
    resolution_full: tuple = RESOLUTION_FULL
    resolution_reduced: tuple = RESOLUTION_REDUCED

    @staticmethod
    def from_env(env: dict | None = None) -> "RenderConfig":
        e = os.environ if env is None else env
        return RenderConfig(
            pymol_bin=e.get("BAT3_RENDER_PYMOL_BIN") or shutil.which("pymol"),
            total_budget_s=int(e.get("BAT3_RENDER_TOTAL_BUDGET_S", TOTAL_BUDGET_S_DEFAULT)),
            system_timeout_s=int(e.get("BAT3_RENDER_SYSTEM_TIMEOUT_S", SYSTEM_TIMEOUT_S_DEFAULT)),
            segment_timeout_s=int(e.get("BAT3_RENDER_SEGMENT_TIMEOUT_S", SEGMENT_TIMEOUT_S_DEFAULT)),
            reduced_style_at_atoms=int(e.get("BAT3_RENDER_REDUCED_AT_ATOMS", REDUCED_STYLE_ATOMS_DEFAULT)),
        )


@dataclass(frozen=True)
class RenderSpec:
    """One planned image: which mmcif, which output, which style, what timeout."""

    label: str           # "system" or segment name — used for path recording
    is_system: bool
    mmcif_path: Path
    png_path: Path
    style: str           # "full" | "reduced"
    timeout_s: int


@dataclass
class RenderOutcome:
    label: str
    is_system: bool
    png_path: Path
    style: str
    ok: bool
    skipped: bool = False                # budget exhausted, never attempted
    error: str | None = None             # failure / timeout reason
    elapsed_s: float = 0.0


# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------

def plan_renders(run_root: Path, segments: list[str], n_atoms: int | None,
                 cfg: RenderConfig) -> list[RenderSpec]:
    """Plan all renders. Pure: deterministic from its arguments.

    System first (full or reduced style based on n_atoms), then one full-style
    image per segment. Images whose mmcif simply does not exist are dropped
    here (they get a warning upstream via the missing count if any).
    """
    render_dir = run_root / RENDER_DIRNAME
    specs: list[RenderSpec] = []

    system_mmcif = run_root / "system.mmcif"
    reduced = bool(n_atoms is not None and n_atoms >= cfg.reduced_style_at_atoms)
    if system_mmcif.is_file():
        specs.append(RenderSpec(
            label="system",
            is_system=True,
            mmcif_path=system_mmcif,
            png_path=render_dir / "system.png",
            style="reduced" if reduced else "full",
            timeout_s=cfg.system_timeout_s,
        ))
    for seg in segments:
        seg_mmcif = run_root / f"{seg}.mmcif"
        if seg_mmcif.is_file():
            specs.append(RenderSpec(
                label=seg,
                is_system=False,
                mmcif_path=seg_mmcif,
                png_path=render_dir / SEGMENTS_DIRNAME / f"{seg}.png",
                style="full",
                timeout_s=cfg.segment_timeout_s,
            ))
    return specs


def build_pymol_script(spec: RenderSpec, cfg: RenderConfig) -> str:
    """Deterministic PyMOL batch script for one image. Pure.

    Mirrors the Mol* MVS default view (MolstarViewer.tsx):
    proteins cartoon, non-polymer ball-and-stick, chain colouring,
    transparent background. Reduced style: cartoon-only proteins, no
    hydrogens/spheres/sticks — bounded cost for >=1M atom systems.
    """
    w, h = cfg.resolution_full if spec.style == "full" else cfg.resolution_reduced
    lines = [
        f"load {spec.mmcif_path}",
        "hide everything, hydro",
        "show cartoon, polymer.protein",
        "util.cbc polymer.protein and elem C",
    ]
    if spec.style == "full":
        lines += [
            "select ligands, organic and not solvent",
            "show sticks, ligands",
            "set_bond stick_radius, 0.18, ligands",
            "show spheres, (elem_Mg+Ca+Na+K+Cl+Zn+Fe+Mn+Cu+Co+Ni)",
            "set sphere_scale, 0.35, (elem_Mg+Ca+Na+K+Cl+Zn+Fe+Mn+Cu+Co+Ni)",
        ]
    lines += [
        "set opaque_background, 0",
        "set ray_opaque_background, 0",
        "set antialias, 2",
        "set ray_trace_mode, 1",
        "orient",
        "center",
        f"png {spec.png_path}, width={w}, height={h}, dpi=150, ray=1",
        "quit",
    ]
    return "\n".join(lines) + "\n"


def summarize(outcomes: list[RenderOutcome]) -> dict:
    """Pure step summary from outcomes."""
    rendered = sum(1 for o in outcomes if o.ok)
    failed = sum(1 for o in outcomes if not o.ok and not o.skipped)
    skipped = sum(1 for o in outcomes if o.skipped)
    return {"rendered": rendered, "failed": failed, "skipped": skipped,
            "total": len(outcomes)}


# ---------------------------------------------------------------------------
# IO shell
# ---------------------------------------------------------------------------

def render_image(spec: RenderSpec, cfg: RenderConfig,
                 timeout_s: int | None = None) -> RenderOutcome:
    """Render one image via `pymol -cq`. Never raises for render failures."""
    if not cfg.pymol_bin:
        return RenderOutcome(spec.label, spec.is_system, spec.png_path,
                             spec.style, ok=False,
                             error="pymol_unavailable")
    spec.png_path.parent.mkdir(parents=True, exist_ok=True)
    script = build_pymol_script(spec, cfg)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [cfg.pymol_bin, "-cq", "-"],
            input=script.encode(), capture_output=True,
            timeout=timeout_s if timeout_s is not None else spec.timeout_s,
        )
        if proc.returncode != 0 or not spec.png_path.is_file():
            tail = (proc.stderr or proc.stdout or b"")[-800:].decode("utf-8", "ignore")
            return RenderOutcome(spec.label, spec.is_system, spec.png_path,
                                 spec.style, ok=False,
                                 error=f"pymol exited {proc.returncode}: {tail}",
                                 elapsed_s=time.monotonic() - start)
        return RenderOutcome(spec.label, spec.is_system, spec.png_path,
                             spec.style, ok=True,
                             elapsed_s=time.monotonic() - start)
    except subprocess.TimeoutExpired:
        return RenderOutcome(spec.label, spec.is_system, spec.png_path,
                             spec.style, ok=False,
                             error=f"timeout after {spec.timeout_s}s",
                             elapsed_s=time.monotonic() - start)
    except Exception as exc:  # shield the pipeline; caller warns
        return RenderOutcome(spec.label, spec.is_system, spec.png_path,
                             spec.style, ok=False,
                             error=f"{type(exc).__name__}: {exc}",
                             elapsed_s=time.monotonic() - start)


def render_all(specs: list[RenderSpec], cfg: RenderConfig) -> list[RenderOutcome]:
    """Render the whole plan under a single total wall-clock budget.

    Images after budget exhaustion are reported skipped (not failed).
    """
    outcomes: list[RenderOutcome] = []
    deadline = time.monotonic() + cfg.total_budget_s
    for spec in specs:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            outcomes.append(RenderOutcome(spec.label, spec.is_system,
                                          spec.png_path, spec.style,
                                          ok=False, skipped=True,
                                          error="total budget exhausted"))
            continue
        budget = min(float(spec.timeout_s), remaining)
        outcomes.append(render_image(spec, cfg, timeout_s=int(max(1, budget))))
    return outcomes
