"""Headless PyMOL PNG renderers for the render_png pipeline task (v3.137).

Why this exists: MolstarViewer (UI) falls back to /files/<run>/render/system.png
(and, post-v3.137, render/segments/<seg>.png) whenever the interactive Mol*
view times out or the system is too large. Nobody generated those PNGs before
this module. Design rules (user ruling 2026-10-19):

- Renders FROM the exported mmcifs (system.mmcif / <seg>.mmcif at run root)
  so the static image depicts exactly what Mol* would show.
- Style (2026-11-10 touch-up): chain-coloured cartoons, ball-and-stick
  ligands, ion spheres, faint bulk lipids shown side-on, water hidden, soft
  lighting with outlines, transparent background. HUGE systems (>= REDUCED_STYLE_ATOMS) degrade to a cheaper
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
# W3.2 item 2: 900 -> 300. F14 (2952 tiny lipid segments) burned the whole
# 900 s budget on 1998 UI-fallback PNGs while the fleet kills runs at 3 h
# with 2 pipelines per worker — the budget must bound the stage wall
# (PyMOL work + deferred recording) so F14-class export+render stays
# under 600 s. Fleets wanting more fallback images override via
# BAT3_RENDER_TOTAL_BUDGET_S.
TOTAL_BUDGET_S_DEFAULT = 300
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


#: Protein chain colours, in order of appearance (greens/blues/ambers that sit
#: well next to the UI's brand green; the ion colour is the UI's --vm-scene-ion).
PROTEIN_PALETTE = ("0x3b8f5a", "0x3d7bbf", "0xc98a3a", "0x8a6fc0",
                   "0xc2546a", "0x3f9e9e", "0x7a8f3b", "0x5b6fb3")
NUCLEIC_COLOR, NUCLEIC_RING_COLOR = "0xe0873a", "0xf2c493"
LIGAND_CARBON_RGB = (0.84, 0.24, 0.47)
ION_COLOR = "0x8a6fc0"
LIPID_COLOR, LIPID_HEAD_COLOR = "0xb8bec6", "0xd9b38c"
#: A non-polymer residue name with at least this many copies is bulk
#: (membrane lipids, cosolvent) and drawn faintly rather than as a ligand.
BULK_MIN_COPIES = 10

# Classification and per-chain colouring need PyMOL's Python API; everything
# else is plain pml. Selections: prot, na, ligand, ion, bulk (water is hidden).
_CLASSIFY = """python
from collections import Counter
from pymol import cmd
res = set()
cmd.iterate("organic and not polymer and not solvent", "res.add((chain, segi, resi, resn))", space={"res": res})
bulk = sorted(n for n, c in Counter(r[3] for r in res).items() if c >= %(bulk_min)d)
cmd.select("bulk", ("organic and not polymer and resn " + "+".join(bulk)) if bulk else "none")
cmd.select("ligand", "organic and not polymer and not solvent and not bulk")
cmd.select("ion", "inorganic and not solvent")
cmd.select("prot", "polymer.protein")
cmd.select("na", "polymer.nucleic")
keys = []
cmd.iterate("prot and name CA", "keys.append((chain, segi))", space={"keys": keys})
palette = %(palette)r
for i, (ch, sg) in enumerate(dict.fromkeys(keys)):
    cmd.color(palette[i %% len(palette)], "prot and chain '%%s' and segi '%%s'" %% (ch, sg))
python end"""

# Membrane systems: a side view of the membrane patch around the
# macromolecules (bulk residues within BULK_PATCH_A of them; the whole slab
# of a periodic box runs off the frame when the protein sits near its edge);
# otherwise the macromolecules (and ligands/ions) fill the frame.
BULK_PATCH_A = 25

_FRAME = """python
from pymol import cmd
if cmd.count_atoms("bulk") and cmd.count_atoms("prot or na or ligand"):
    cmd.select("patch", "byres (bulk within %(patch)d of (prot or na or ligand))")
    cmd.hide("everything", "bulk and not patch")
    cmd.orient("patch")
    cmd.turn("x", -90)
    cmd.zoom("prot or na or ligand or patch", 1, complete=1)
elif cmd.count_atoms("prot or na or ligand or ion"):
    cmd.orient("prot or na or ligand or ion")
    cmd.zoom("prot or na or ligand or ion", 0.5, complete=1)
else:
    cmd.orient("all")
    cmd.zoom("all", 0.5, complete=1)
python end"""


def build_pymol_script(spec: RenderSpec, cfg: RenderConfig) -> str:
    """Deterministic PyMOL batch script for one image. Pure.

    Polymers as cartoon coloured by chain (nucleic acids orange with filled
    base rings), ligands ball-and-stick with magenta carbons, ions as
    spheres, bulk lipids as faint sticks with phosphate beads (membranes
    shown side-on), water and hydrogens hidden; soft lighting with outlines
    on a transparent background. Reduced style (>=1M atoms): polymer
    cartoons only — bounded cost.
    """
    w, h = cfg.resolution_full if spec.style == "full" else cfg.resolution_reduced
    lines = [
        f"load {spec.mmcif_path}",
        "hide everything",
        "remove hydro",
        _CLASSIFY % {"bulk_min": BULK_MIN_COPIES, "palette": PROTEIN_PALETTE},
        "show cartoon, prot or na",
        f"color {NUCLEIC_COLOR}, na",
        f"set cartoon_ring_color, {NUCLEIC_RING_COLOR}",
        "set cartoon_ring_mode, 3",
        "set cartoon_ring_finder, 1",
        "set cartoon_nucleic_acid_mode, 4",
        "set cartoon_fancy_helices, 1",
        "set cartoon_smooth_loops, 1",
    ]
    if spec.style == "full":
        r, g, b = LIGAND_CARBON_RGB
        lines += [
            f"set_color ligand_carbon, [{r}, {g}, {b}]",
            "show sticks, ligand",
            "show spheres, ligand",
            "set stick_radius, 0.28, ligand",
            "set sphere_scale, 0.3, ligand",
            "util.cbag ligand",
            "color ligand_carbon, ligand and elem C",
            "show spheres, ion",
            "set sphere_scale, 0.55, ion",
            f"color {ION_COLOR}, ion",
            "show sticks, bulk",
            "set stick_radius, 0.12, bulk",
            "set stick_transparency, 0.6, bulk",
            f"color {LIPID_COLOR}, bulk",
            "show spheres, bulk and elem P",
            "set sphere_scale, 0.9, bulk and elem P",
            "set sphere_transparency, 0.25, bulk and elem P",
            f"color {LIPID_HEAD_COLOR}, bulk and elem P",
        ]
    lines += [
        _FRAME % {"patch": BULK_PATCH_A},
        "set ray_trace_mode, 1",
        "set ray_trace_color, 0x2a2f36",
        "set ray_trace_gain, 0.08",
        "set ray_shadow, 0",
        "set ambient, 0.45",
        "set direct, 0.55",
        "set reflect, 0.25",
        "set specular, 0.18",
        "set shininess, 30",
        "set depth_cue, 1",
        "set fog_start, 0.75",
        "set opaque_background, 0",
        "set ray_opaque_background, 0",
        "set antialias, 2",
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
    # pymol-open-source does NOT consume a script from stdin (`pymol -cq -`
    # silently no-ops, verified 2026-10-19): feed a .pml file instead.
    import tempfile
    fd, script_path = tempfile.mkstemp(suffix=".pml",
                                       dir=str(spec.png_path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(script)
    except Exception:
        os.unlink(script_path)
        raise
    try:
        try:
            proc = subprocess.run(
                [cfg.pymol_bin, "-cq", script_path],
                capture_output=True,
                timeout=timeout_s if timeout_s is not None else spec.timeout_s,
            )
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass
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
    if proc.returncode != 0 or not spec.png_path.is_file():
        tail = (proc.stderr or proc.stdout or b"")[-800:].decode("utf-8", "ignore")
        return RenderOutcome(spec.label, spec.is_system, spec.png_path,
                             spec.style, ok=False,
                             error=f"pymol exited {proc.returncode}: {tail}",
                             elapsed_s=time.monotonic() - start)
    return RenderOutcome(spec.label, spec.is_system, spec.png_path,
                         spec.style, ok=True,
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
