"""3.9 — A-15: MDDBR downloader file selection (ranked topology, PDB always,
never trajectory.bin)."""
from __future__ import annotations

import itertools

import pytest

mddbr_client = pytest.importorskip("mddbr_client")


def _files(names):
    return [{"filename": n, "length": 1, "internalId": f"id{i}"} for i, n in enumerate(names)]


class TestA15TopologyRanking:
    @pytest.mark.parametrize("order", list(itertools.permutations(
        ["topol.top", "ff.itp", "system.prmtop"])))
    def test_prmtop_wins_any_order(self, order):
        top, _, _ = mddbr_client._choose_files(_files(list(order) + ["trajectory.xtc"]))
        assert top["filename"] == "system.prmtop", order

    def test_tpr_beats_prmtop(self):
        top, _, _ = mddbr_client._choose_files(_files(["system.prmtop", "system.tpr"]))
        assert top["filename"] == "system.tpr"

    def test_psf_beats_top_and_itp(self):
        top, _, _ = mddbr_client._choose_files(_files(["topol.top", "ff.itp", "system.psf"]))
        assert top["filename"] == "system.psf"


class TestA15TrajectoryAndPdb:
    def test_bin_never_selected(self):
        top, pdb, traj = mddbr_client._choose_files(
            _files(["system.prmtop", "trajectory.bin", "structure.pdb"]))
        assert top["filename"] == "system.prmtop"
        assert traj is None, "trajectory.bin is unreadable by every strategy (A-15)"
        assert pdb is not None and pdb["filename"] == "structure.pdb"

    def test_pdb_always_fallback_present(self):
        # with a topology present the PDB must still be chosen (download list
        # includes it as cross-kind coordinate fallback)
        _, pdb, _ = mddbr_client._choose_files(
            _files(["system.tpr", "structure.pdb"]))
        assert pdb is not None

    def test_pdb_only_survives(self):
        top, pdb, traj = mddbr_client._choose_files(_files(["structure.pdb"]))
        assert top is None and pdb is not None and traj is None

    def test_preferred_trajectory_names_first(self):
        _, _, traj = mddbr_client._choose_files(
            _files(["chunk000.xtc", "trajectory.xtc", "system.tpr"]))
        assert traj["filename"] == "trajectory.xtc"
