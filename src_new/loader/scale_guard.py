"""Universal coordinate-scale guard for loaded universes.

Detects Angstrom/nanometre coordinate collapse on ANY loaded Universe using
geometric evidence only — bond-length medians and bounding-box density —
and never the reader's reported units. Reader units describe native *file*
units and lie about what reaches consumers (observed Phase 0, 2026-10-21:
GRO readers report 'nm' while delivering Angstroms; MDAnalysis 2.10.0's new
TPRReader delivers literal nm — upstream MDAnalysis/mdanalysis#5374, fixed
for 2.11; box vectors are read then discarded — #5466, also 2.11).

A clean nm->Angstrom (x10) collapse is corrected IN PLACE (positions,
velocities, and — when the reader discarded it — the GROMACS box). Any
candidate that is not a clean x10 is reported and left untouched:
fail loud, never silently wrong.

Phase-0 evidence (status ledger 2026-10-21):
  healthy bond-len median   ~0.95-2.4 A     collapsed specimen 0.0964 A
  healthy bbox density      10.2-36.9 A^3/atom  collapsed 0.0161  (630-2300x)
  degenerate-clash system   25.6 A^3/atom -> density alone is clash-safe
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

import numpy as np

logger = logging.getLogger(__name__)

# --- detection thresholds (margins chosen from Phase-0 measurements) ---
MIN_BONDS_FOR_SIGNAL = 20           # below this, bond signal is unreliable
MIN_ATOMS_FOR_DENSITY = 100         # below this, bbox density is meaningless
BOND_MEDIAN_COLLAPSED_MAX_ANG = 0.4     # healthy systems start ~0.95 A
BOND_MEDIAN_POST_SCALE_RANGE = (0.7, 3.5)   # validity gate after x10
DENSITY_COLLAPSED_MAX_A3_PER_ATOM = 1.0     # healthy band is 10-40
DENSITY_POST_SCALE_RANGE = (2.0, 200.0)     # self-check after x10
NM_TO_ANGSTROM = 10.0
MAX_BOND_SAMPLE = 50_000

WARN_RESCALED_EXPECTED = "coords_rescaled_nm_to_angstrom"
WARN_RESCALED_UNEXPECTED = "coords_rescaled_unexpected"
WARN_SCALE_ANOMALOUS = "geometry_scale_anomalous"

# Strategy values where collapse is the *known upstream-bug* path; anything
# else corrected by geometry is a NEW broken reader path and gets the loud code.
_EXPECTED_COLLAPSE_STRATEGIES = {"gromacs_tpr"}


@dataclass
class ScaleGuardReport:
    """Outcome of the scale guard; persisted to results (loading/scale_correction)."""

    checked: bool
    corrected: bool = False
    factor: float = 1.0
    signal: str | None = None            # 'bond_median' | 'density'
    bond_median: float | None = None
    density_a3_per_atom: float | None = None
    box_attached: bool = False
    warning_code: str | None = None
    warning_message: str | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _bond_length_median(universe, positions: np.ndarray) -> float | None:
    """Median bonded-atom distance, sampled; None when too few bonds."""
    try:
        bonds = universe.atoms.bonds
        indices = bonds.indices
    except Exception:  # NoDataError / attribute absence on bondless topology
        return None
    n = len(indices)
    if n < MIN_BONDS_FOR_SIGNAL:
        return None
    if n > MAX_BOND_SAMPLE:
        pick = np.linspace(0, n - 1, MAX_BOND_SAMPLE).astype(np.int64)
        indices = indices[pick]
    d = np.linalg.norm(positions[indices[:, 0]] - positions[indices[:, 1]], axis=1)
    d = d[np.isfinite(d)]
    if len(d) < MIN_BONDS_FOR_SIGNAL:
        return None
    return float(np.median(d))


def _bbox_density(positions: np.ndarray) -> float | None:
    """Bounding-box volume per atom in A^3; None for tiny/degenerate inputs."""
    if len(positions) < MIN_ATOMS_FOR_DENSITY:
        return None
    span = positions.max(axis=0) - positions.min(axis=0)
    if not np.all(np.isfinite(span)):
        return None
    return float(np.prod(span) / len(positions))


def _detect(universe) -> ScaleGuardReport:
    """Geometric detection; pure (no mutation)."""
    positions = universe.atoms.positions
    bond_median = _bond_length_median(universe, positions)
    density = _bbox_density(positions)

    report = ScaleGuardReport(
        checked=True,
        bond_median=bond_median,
        density_a3_per_atom=density,
    )

    # Primary: bonded geometry
    if bond_median is not None:
        if bond_median >= BOND_MEDIAN_COLLAPSED_MAX_ANG:
            return report  # healthy geometry, no correction
        scaled = bond_median * NM_TO_ANGSTROM
        lo, hi = BOND_MEDIAN_POST_SCALE_RANGE
        if lo <= scaled <= hi:
            return _candidate(report, "bond_median")
        return _anomaly(report, f"bond median {bond_median:.3f} A is implausible "
                               f"and not a clean x10 collapse (x10 -> {scaled:.3f} A)")

    # Fallback: bounding-box density (bondless systems: waters, ions)
    if density is not None:
        if density >= DENSITY_COLLAPSED_MAX_A3_PER_ATOM:
            return report  # healthy density
        lo, hi = DENSITY_POST_SCALE_RANGE
        scaled = density * NM_TO_ANGSTROM ** 3
        if lo <= scaled <= hi:
            return _candidate(report, "density")
        return _anomaly(report, f"bbox density {density:.4f} A^3/atom is implausible "
                               f"and not a clean x10 collapse (x1000 -> {scaled:.2f})")

    report.note = "insufficient geometry evidence (no bonds, too few atoms); not checked"
    report.checked = False
    return report


def _candidate(report: ScaleGuardReport, signal: str) -> ScaleGuardReport:
    report.signal = signal
    report.factor = NM_TO_ANGSTROM
    return report


def _anomaly(report: ScaleGuardReport, why: str) -> ScaleGuardReport:
    report.warning_code = WARN_SCALE_ANOMALOUS
    report.warning_message = (
        "Coordinate scale looks unusual and was LEFT UNCHANGED: " + why + ". "
        "Inspect the input files; downstream geometry may be degraded."
    )
    return report


def _apply_factor(universe, factor: float) -> None:
    """Scale positions (and velocities when present) in place."""
    ts = universe.trajectory.ts
    ts.positions = ts.positions * factor
    if getattr(ts, "has_velocities", False) and ts.velocities is not None:
        ts.velocities = ts.velocities * factor
    # when the reader attached a box, keep it consistent with the rescale
    dims = getattr(universe, "dimensions", None)
    if dims is not None and len(dims) >= 3:
        scaled = np.asarray(dims, dtype=np.float32).copy()
        scaled[:3] *= factor
        ts.dimensions = scaled


def _try_attach_gromacs_box(universe, factor: float, source_files: dict | None) -> bool:
    """Best-effort box recovery for TPR-only loads (MDAnalysis<=2.10 discards it).

    Only called on the correction path, so native tpr box vectors (nm) are
    scaled by the same factor as positions. Never raises; never overwrites
    an existing box. The tpr path comes from the load's *source files* when
    the reader is in-memory (filename unavailable there).
    """
    if getattr(universe, "dimensions", None) is not None:
        return False
    filename = getattr(getattr(universe, "trajectory", None), "filename", None)
    if not filename and source_files:
        for key, path in source_files.items():
            if str(key).lower().endswith("tpr") or str(path).lower().endswith(".tpr"):
                filename = path
                break
    if not filename:
        return False
    try:
        from MDAnalysis.lib import util as mda_util
        from MDAnalysis.lib.mdamath import triclinic_box
        from MDAnalysis.topology.tpr import setting as tpr_setting
        from MDAnalysis.topology.tpr import utils as tpr_utils

        with mda_util.openany(filename, mode="rb") as handle:
            data = tpr_utils.TPXUnpacker(handle.read())
        header = tpr_utils.read_tpxheader(data)
        if not header.bBox:
            return False
        if header.fver >= tpr_setting.tpxv_AddSizeField and header.fgen >= 27:
            data = tpr_utils.TPXUnpacker2020.from_unpacker(data)
        box = tpr_utils.extract_box_info(data, header.fver)
        vectors = np.asarray(box.size, dtype=np.float64)
        if vectors.shape != (3, 3) or not np.all(np.isfinite(vectors)) or not np.any(vectors):
            return False
        dims = np.array(triclinic_box(*vectors), dtype=np.float32)
        dims[:3] *= factor
        universe.trajectory.ts.dimensions = dims
        return True
    except Exception as exc:
        logger.warning("scale_guard: box recovery failed (%s); proceeding without box", exc)
        return False


_FROM_POSITIONS_MIN_ATOMS = MIN_ATOMS_FOR_DENSITY


def geometry_status_from_positions(positions: np.ndarray) -> dict:
    """Density-based geometry status for a positions array (export-time record).

    Mirrors the client-side probe in ui/.../geometry-check.ts so server and
    UI use identical thresholds (Phase-0 evidence: healthy 10-40 A^3/atom,
    collapsed 0.016; cutoff 1.0).
    """
    n = len(positions)
    if n < _FROM_POSITIONS_MIN_ATOMS:
        return {"status": "ok", "atom_count": n, "density_a3_per_atom": None}
    span = positions.max(axis=0) - positions.min(axis=0)
    if not np.all(np.isfinite(span)):
        return {"status": "unknown", "atom_count": n, "density_a3_per_atom": None}
    density = float(np.prod(span) / n)
    return {
        "status": "degenerate" if density < DENSITY_COLLAPSED_MAX_A3_PER_ATOM else "ok",
        "atom_count": n,
        "density_a3_per_atom": density,
        "span": [float(x) for x in span],
    }


def run_scale_guard(universe, strategy=None, source_files: dict | None = None) -> ScaleGuardReport:
    """Detect and heal nm-collapsed coordinates on a freshly loaded Universe.

    Universal: intended to run for EVERY strategy right after the success
    gates. No-op (checked, not corrected) on healthy Angstrom geometry.
    `strategy` only selects the warning severity (known-tpr path vs new
    broken-reader path); the correction decision is geometry-only.
    `source_files` (strategy-selected inputs) enables box recovery when the
    coordinate reader is in-memory.
    """
    report = _detect(universe)

    if report.signal is None:
        return report  # healthy, anomalous (already coded), or not checked

    # correction path
    _apply_factor(universe, report.factor)
    report.corrected = True
    report.box_attached = _try_attach_gromacs_box(universe, report.factor, source_files)

    # self-check on the corrected geometry (fail loud if we were wrong)
    post_density = _bbox_density(universe.atoms.positions)
    if post_density is not None:
        lo, hi = DENSITY_POST_SCALE_RANGE
        if not (lo <= post_density <= hi):
            report.warning_code = WARN_SCALE_ANOMALOUS
            report.warning_message = (
                f"Coordinates were rescaled x{report.factor:g} but the corrected system "
                f"still looks implausible ({post_density:.2f} A^3/atom). Inspect inputs."
            )
            return report

    strategy_value = getattr(strategy, "value", strategy)
    expected = strategy_value in _EXPECTED_COLLAPSE_STRATEGIES
    report.warning_code = WARN_RESCALED_EXPECTED if expected else WARN_RESCALED_UNEXPECTED
    which = "bond-length median" if report.signal == "bond_median" else "bonding-box density"
    report.warning_message = (
        f"Input coordinates appeared to be in nanometres ({which} evidence) and were "
        f"converted to angstroms (x{report.factor:g})."
        + ("" if expected else " This input format is not expected to need rescaling - "
                               "please verify the uploaded files.")
    )
    return report
