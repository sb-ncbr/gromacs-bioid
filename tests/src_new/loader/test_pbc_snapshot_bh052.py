"""BH-052 — the frame-0 snapshot must preserve unwrap corrections.

A-17.1 tried to lock the corrected frame into memory with
``transfer_to_memory(start=0, stop=1)`` — but that re-reads frame 0 from
DISK and silently discards the in-memory unwrap corrections. A wrapped
multi-frame trajectory (per-atom wrapping, e.g. trjconv -pbc atom) kept
bonds split across the box (67 A on the M13 twin) while the report
claimed ``unwrapped: True``, producing wrong stereochemistry and a wrong
InChIKey (DOAKLVKFURWEDJ-GJQQYXTFSA-K instead of -HOASTROESA-K).

Fix: snapshot the corrected positions with ``load_new(...,
format="memory")``; self-check that no bonded pair remains above 4 A and
flip ``unwrapped`` to False with a warning if any does, so the report
cannot claim success while molecules are still split.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import MDAnalysis as mda
import pytest

from src_new.config.loader import RunConfig
from src_new.loader.unwrap import PbcRepair

DATA = Path(__file__).resolve().parents[2] / "data"
M13_DIR = Path(
    "/home/tomsko/work/bat3_article_reviews/bioid_bughunt/testcases/"
    "M13_daptomycin_amber/input")


def _wrapped_xtc(tmp_path: Path, n_frames: int = 3) -> Path:
    """A multi-frame XTC whose frame 0 is M13 wrapped per-atom into an
    artificial box (molecule cut at the periodic boundary). M13's authored
    bonds are all <= 1.7 A, so any post-unwrap bond above 4 A is a PBC
    artefact, not input geometry."""
    u = mda.Universe(str(M13_DIR / "topology.prmtop"),
                     str(M13_DIR / "structure.pdb"))
    pos = u.atoms.positions
    lo, hi = pos.min(axis=0), pos.max(axis=0)
    dims = np.array([2 * (hi[0] - lo[0]) + 10, 2 * (hi[1] - lo[1]) + 10,
                     2 * (hi[2] - lo[2]) + 10, 90, 90, 90], dtype=np.float32)
    u.dimensions = dims
    u.atoms.positions -= (u.atoms.center_of_mass()
                           - np.array([1.0, 1.0, 1.0]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        u.atoms.wrap()
    out = tmp_path / "traj.xtc"
    arr = np.repeat(u.atoms.positions.astype(np.float32)[np.newaxis, :, :],
                    n_frames, axis=0)
    seg = mda.Universe.empty(len(u.atoms), trajectory=True)
    seg.load_new(arr, format="memory")
    seg.dimensions = dims
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with mda.Writer(str(out), n_atoms=len(u.atoms)) as w:
            for _ in range(n_frames):
                w.write(seg.atoms)
    return out


def _max_bond(u) -> tuple[float, int]:
    b = u.bonds.to_indices()
    d = np.linalg.norm(u.atoms.positions[b[:, 0]] - u.atoms.positions[b[:, 1]],
                      axis=1)
    return float(d.max()), int((d > 4.0).sum())


class TestMultiframeWrappedXtc:
    def test_snapshot_keeps_unwrap_corrections(self, tmp_path):
        """RED at d274285af: the snapshot re-read the raw frame from
        disk, so the unwrapped positions were discarded."""
        xtc = _wrapped_xtc(tmp_path)
        u = mda.Universe(str(M13_DIR / "topology.prmtop"), str(xtc))
        raw_max, raw_over = _max_bond(u)
        assert raw_over > 0, "fixture should be cut at the boundary"

        # reference: what unwrap(compound='fragments', reference='com')
        # produces in memory
        u_ref = mda.Universe(str(M13_DIR / "topology.prmtop"), str(xtc))
        u_ref.atoms.unwrap(compound='fragments', reference='com')
        ref_pos = u_ref.atoms.positions.copy()
        ref_max, ref_over = _max_bond(u_ref)
        assert ref_over == 0 and ref_max < 2.0

        report = PbcRepair(u, RunConfig()).run()
        post_max, post_over = _max_bond(u)
        assert post_over == 0, (f"bonded pairs still split across the box "
                                f"after the pbc stage: max {post_max:.1f} A")
        assert post_max < 2.0
        assert u.trajectory.n_frames == 1, "frame-0 snapshot must lock 1 frame"
        np.testing.assert_allclose(u.atoms.positions, ref_pos, atol=1e-3)
        assert report.unwrapped is True
        assert report.unwrap_incomplete is False

    def test_report_cannot_lie_about_broken_bonds(self, tmp_path):
        """Self-check path: two atoms bonded 27 A apart in a 20 A box can
        never be made whole; the report must say unwrapped=False and warn
        with the count and the maximum, instead of claiming success."""
        u = mda.Universe.empty(2, n_residues=1, atom_resindex=[0, 0],
                               residue_segindex=[0], trajectory=True)
        u.add_TopologyAttr('type', ['C', 'C'])
        u.add_TopologyAttr('resname', ['LIG'])
        u.add_TopologyAttr('name', ['C1', 'C2'])
        u.add_TopologyAttr('bonds', [(0, 1)])
        u.load_new(np.array([[0.0, 0.0, 0.0], [27.0, 0.0, 0.0]],
                            dtype=np.float32), format="memory")
        u.dimensions = np.array([20.0, 20.0, 20.0, 90, 90, 90])

        report = PbcRepair(u, RunConfig()).run()
        assert report.unwrapped is False
        assert report.unwrap_incomplete is True
        assert report.post_unwrap_bonds_over_4a == 1
        assert report.post_unwrap_max_bond_length > 4.0
        assert any("pbc_unwrap_incomplete" in w for w in report.warnings)


class TestSingleFrameStructure:
    def test_single_frame_reader_unchanged(self):
        """Single-frame readers never take the snapshot path (no frame
        locking); PbcRepair must correct them in place exactly as a
        manual unwrap would. A 1-frame XTC is the single-frame analogue
        of the multi-frame regression above."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            xtc = _wrapped_xtc(Path(td), n_frames=1)
            u_ref = mda.Universe(str(M13_DIR / "topology.prmtop"), str(xtc))
            u_ref.atoms.unwrap(compound='fragments', reference='com')
            expected = u_ref.atoms.positions.copy()
            u = mda.Universe(str(M13_DIR / "topology.prmtop"), str(xtc))
            report = PbcRepair(u, RunConfig()).run()
            post_max, post_over = _max_bond(u)
            assert post_over == 0 and post_max < 2.0
            np.testing.assert_allclose(u.atoms.positions, expected, atol=1e-3)
            assert u.trajectory.n_frames == 1
            assert report.error is None
            assert report.unwrapped is True
            assert not any("snapshot" in w for w in report.warnings)
