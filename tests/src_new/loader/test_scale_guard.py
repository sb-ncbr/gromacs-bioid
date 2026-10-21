"""Universal coordinate-scale guard (src_new/loader/scale_guard.py).

Regression wave 2026-10-21 (run a5b785cc): MDAnalysis 2.10.0's new TPRReader
delivers coordinates in *nanometres* (upstream MDAnalysis/mdanalysis#5374)
and discards the box (#5466). The collapsed geometry then poisoned exports
(OSM: 0.016 A^3/atom vs healthy 10-40) and blew up Mol* bond inference in the
UI. Detection here is geometry-only (bond medians / bbox density) — reader
`units` is native-file metadata and provably unreliable (GRO reports 'nm'
while delivering angstroms).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")

from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager
from src_new.loader.scale_guard import (
    DENSITY_COLLAPSED_MAX_A3_PER_ATOM,
    WARN_RESCALED_EXPECTED,
    WARN_RESCALED_UNEXPECTED,
    WARN_SCALE_ANOMALOUS,
    run_scale_guard,
)
from src_new.loader.strategies import LoadStrategy, load_simulation

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
TPR_ONLY_DIR = DATA_DIR / "gromacs_tpr_only"
PSF_DIR = DATA_DIR / "charmm_psf_pdb"


# ---------------------------------------------------------------- helpers ----

def _bonded_universe(positions: np.ndarray, n_bonds: int | None = None):
    """Universe with consecutive-pair bonds at the given positions."""
    n = len(positions)
    u = mda.Universe.empty(n, n_residues=1, trajectory=True)
    u.atoms.positions = positions.astype(np.float32)
    if n_bonds is None:
        n_bonds = max(n - 1, 0)
    bonds = [(i, i + 1) for i in range(min(n_bonds, n - 1))]
    if bonds:
        u.add_TopologyAttr("bonds", bonds)
    return u


def _chain_positions(n: int, bond_len: float) -> np.ndarray:
    """Linear chain: every bonded pair exactly bond_len apart."""
    return np.column_stack([np.arange(n) * bond_len, np.zeros(n), np.zeros(n)])


def _grid_positions(spacing: float, side: int = 8) -> np.ndarray:
    """3D lattice: consecutive-index neighbours exactly `spacing` apart, and
    a sane (non-degenerate) bounding box — bond signal and density agree."""
    ax = np.arange(side) * spacing
    return np.array(np.meshgrid(ax, ax, ax, indexing="ij")).reshape(3, -1).T


# ------------------------------------------------------------- unit tests ----

class TestHealthySystemsAreUntouched:
    def test_bonded_angstrom_system_not_corrected(self):
        pos = _grid_positions(1.5)
        u = _bonded_universe(pos)
        report = run_scale_guard(u, LoadStrategy.CHARMM_PSF_PDB)
        assert report.checked and not report.corrected and report.warning_code is None
        np.testing.assert_allclose(u.atoms.positions, pos, atol=1e-5)

    def test_dense_but_angstrom_clashy_system_not_corrected(self):
        """DEGENERATE-clash (A003ZR shape): crushed blob, but globally sane
        density and no bond signal -> must NOT be 'corrected' (would explode it)."""
        rng = np.random.default_rng(7)
        pos = rng.uniform(0, 80, (2000, 3)).astype(np.float32)
        pos[:1500] = pos[:1500] * 0.03 + 40  # clashy blob, no bonds recorded
        u = _bonded_universe(pos, n_bonds=0)
        report = run_scale_guard(u, LoadStrategy.PDB)
        assert not report.corrected
        np.testing.assert_allclose(u.atoms.positions, pos, atol=1e-5)


class TestCollapseDetectionAndCorrection:
    def test_bonded_nm_system_corrected_with_expected_code(self):
        pos = _grid_positions(0.15)  # 0.15 'A' median -> x10 -> 1.5 A
        u = _bonded_universe(pos)
        report = run_scale_guard(u, LoadStrategy.GROMACS_TPR)
        assert report.corrected and report.factor == 10.0
        assert report.signal == "bond_median"
        assert report.warning_code == WARN_RESCALED_EXPECTED
        assert np.linalg.norm(u.atoms.positions[1] - u.atoms.positions[0]) == pytest.approx(1.5, abs=1e-3)

    def test_non_tpr_strategy_gets_loud_code(self):
        pos = _grid_positions(0.15)
        u = _bonded_universe(pos)
        report = run_scale_guard(u, LoadStrategy.PDB)
        assert report.corrected
        assert report.warning_code == WARN_RESCALED_UNEXPECTED

    def test_bondless_nm_system_corrected_via_density(self):
        rng = np.random.default_rng(3)
        pos = rng.uniform(0, 1.2, (800, 3)).astype(np.float32)  # ~0.002 A^3/atom
        u = _bonded_universe(pos, n_bonds=0)
        report = run_scale_guard(u, LoadStrategy.GROMACS_TPR)
        assert report.corrected and report.signal == "density"
        span = u.atoms.positions.max(axis=0) - u.atoms.positions.min(axis=0)
        assert np.prod(span) / len(pos) > DENSITY_COLLAPSED_MAX_A3_PER_ATOM

    def test_velocities_scaled_with_positions(self):
        pos = _grid_positions(0.15)
        u = _bonded_universe(pos)
        vel = np.random.default_rng(1).normal(0, 0.02, pos.shape).astype(np.float32)
        u.trajectory.ts.velocities = vel.copy()
        u.trajectory.ts.has_velocities = True
        report = run_scale_guard(u, LoadStrategy.GROMACS_TPR)
        assert report.corrected
        np.testing.assert_allclose(u.trajectory.ts.velocities, vel * 10.0, rtol=1e-5)


class TestAnomaliesAreReportedNeverMutated:
    def test_non_x10_collapse_left_untouched(self):
        pos = _chain_positions(500, 0.25)  # x10 -> 2.5 A? in band... craft x100: 0.015
        pos = _chain_positions(500, 0.015)  # 0.015 'A' bonds -> x10 -> 0.15 A still absurd
        u = _bonded_universe(pos)
        report = run_scale_guard(u, LoadStrategy.GROMACS_TPR)
        assert not report.corrected
        assert report.warning_code == WARN_SCALE_ANOMALOUS
        np.testing.assert_allclose(u.atoms.positions, pos, atol=1e-6)

    def test_tiny_system_not_checked(self):
        pos = _chain_positions(50, 0.1)  # too few atoms for density, bonds exist though
        u = _bonded_universe(pos, n_bonds=5)  # < MIN_BONDS_FOR_SIGNAL
        report = run_scale_guard(u, LoadStrategy.GROMACS_TPR)
        assert not report.checked and not report.corrected


# ------------------------------------------- strategy-level (real fixture) ----

class TestRealTprFixtureEndToEnd:
    """PE_CL_530Run.tpr (GROMACS 2018.3): the specimen from run a5b785cc."""

    def test_tpr_only_load_rescaled_and_box_recovered(self, tmp_path: Path):
        bundle = inspect_directory(TPR_ONLY_DIR)
        dec = select_best_file_combination(bundle)
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        assert result.success and result.final_strategy == LoadStrategy.GROMACS_TPR

        u = result.universe
        water = u.select_atoms("resname TIP3")
        oh = np.linalg.norm(water.atoms[1].position - water.atoms[0].position)
        assert oh == pytest.approx(0.957, abs=0.05), "water O-H must be ~0.96 A after rescale"

        span = u.atoms.positions.max(axis=0) - u.atoms.positions.min(axis=0)
        assert (span > 50).all(), "system span must be tens of angstroms, not nm-scale"

        assert u.dimensions is not None, "tpr box should be recovered"
        assert np.all(u.dimensions[:3] > 20), "box lengths must be angstrom-scale"

        sr = result.scale_report
        assert sr["corrected"] and sr["factor"] == 10.0
        assert sr["signal"] == "bond_median" and sr["box_attached"]
        assert sr["warning_code"] == WARN_RESCALED_EXPECTED

        persisted = ResultsManager(tmp_path / "r.json").get_data("loading/scale_correction")
        assert persisted["corrected"] is True

    def test_tpr_gro_pairing_not_rescaled(self, tmp_path: Path):
        """tpr+gro loads coordinates through the GRO reader (proper angstroms):
        the guard must leave healthy geometry alone end-to-end."""
        dep = DATA_DIR / "gromacs_tpr_gro"  # tpr + matching gro (58500 atoms, real solvent)
        bundle = inspect_directory(dep)
        dec = select_best_file_combination(bundle)
        if dec is None:
            pytest.skip("tpr+gro pairing not produced by discovery for this bundle")
        result = load_simulation(dec, bundle, RunConfig(), ResultsManager(tmp_path / "r.json"))
        if not result.success or result.final_strategy != LoadStrategy.GROMACS_TPR_GRO:
            pytest.skip(f"pairing resolved differently: {result.final_strategy}")
        sr = result.scale_report
        assert sr is not None and not sr["corrected"] and sr["warning_code"] is None


# ------------------------------------------------- export-time status probe ----

from src_new.loader.scale_guard import geometry_status_from_positions


class TestGeometryStatusFromPositions:
    def test_collapsed_density_flagged(self):
        # a5b785cc shape: 58500 atoms compressed into ~0.016 A^3/atom
        pos = np.random.default_rng(1).uniform(0, 15, (20_000, 3)).astype(np.float32)
        st = geometry_status_from_positions(pos)
        assert st["status"] == "degenerate" and st["density_a3_per_atom"] < 1.0

    def test_healthy_density_ok(self):
        pos = np.random.default_rng(2).uniform(0, 80, (20_000, 3)).astype(np.float32)
        st = geometry_status_from_positions(pos)
        assert st["status"] == "ok" and st["density_a3_per_atom"] > 1.0
        assert st["span"][0] > 40

    def test_tiny_system_ok_no_density(self):
        pos = np.random.default_rng(3).uniform(0, 0.5, (50, 3)).astype(np.float32)
        st = geometry_status_from_positions(pos)
        assert st["status"] == "ok" and st["density_a3_per_atom"] is None
