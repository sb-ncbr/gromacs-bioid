"""W3 B3 (BH-014 rest): honest failure classification for the unknown-kind
fallback, and .ent loads as PDB.

Production evidence (g0a2091-1028):
- F06 ({md.dcd} only) reported "No .tpr files found" — the real problem
  is a TRAJECTORY WITHOUT TOPOLOGY.
- X07 ({conf.xyz}) reported the same wrong message — .xyz is simply an
  UNSUPPORTED extension.
- S26 ({.pdb.gz}) ditto — it is COMPRESSED input.
- X03 ({model.ent}) failed outright even though .ent IS PDB-format
  content and must load as PDB.

Acceptance pinned here:
1. F06's failure summary says missing-topology and names the trajectory
   file — never the bogus "No .tpr files found".
2. X07 says unsupported extension (.xyz), S26 says compressed input
   (.pdb.gz).
3. X03 (.ent) loads successfully via the PDB strategy.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _decision(tmp_path: Path, files: dict[str, str]):
    """Run discovery over a synthetic deposit dir."""
    from src_new.input.discovery import inspect_directory, \
        select_best_file_combination
    d = tmp_path / "input"
    d.mkdir(exist_ok=True)
    for name, content in files.items():
        (d / name).write_text(content)
    bundle = inspect_directory(d)
    return bundle, select_best_file_combination(bundle)


def _run_load(tmp_path: Path, files: dict[str, str]):
    """Full load_simulation against a synthetic deposit; returns
    (LoadingResult, results_manager)."""
    from src_new.config.loader import RunConfig
    from src_new.loader.strategies import load_simulation
    from src_new.results.results_manager import ResultsManager
    bundle, decision = _decision(tmp_path, files)
    results = ResultsManager(str(tmp_path / "results.json"),
                             pipeline_name="b3")
    res = load_simulation(decision=decision, bundle=bundle,
                          config=RunConfig(), results=results)
    return res, results


_MIN_PDB = """\
ATOM      1  N   ALA X   1      11.104   6.134  10.000  1.00 20.00           N
ATOM      2  CA  ALA X   1      12.560   6.300  10.000  1.00 20.00           C
ATOM      3  C   ALA X   1      13.000   7.700  10.000  1.00 20.00           C
ATOM      4  O   ALA X   1      12.400   8.700  10.000  1.00 20.00           O
END
"""

_MIN_DCD = "CORD" + "\x00" * 200  # header-looking bytes; content irrelevant
_MIN_XYZ = "2\nxyz file\nH 0.0 0.0 0.0\nH 0.0 0.0 0.74\n"
_MIN_GZ = "\x1f\x8b\x08" + "\x00" * 40


class TestUnknownKindClassification:
    def test_dcd_only_reports_missing_topology_not_tpr(self, tmp_path):
        res, results = _run_load(tmp_path, {"md.dcd": _MIN_DCD})
        if res.success:  # a dcd cannot stand alone, but stay honest
            pytest.xfail("dcd-only unexpectedly loaded")
        summary = results.get_data("loading/failure_summary")
        assert summary, "failure summary must exist"
        assert summary["reason"] == "missing_topology", summary
        assert "dcd" in summary["message"], summary
        assert "No .tpr files found" not in summary["message"], summary

    def test_xyz_reports_unsupported_extension(self, tmp_path):
        res, results = _run_load(tmp_path, {"conf.xyz": _MIN_XYZ})
        if res.success:
            pytest.xfail("xyz unexpectedly loaded")
        summary = results.get_data("loading/failure_summary")
        assert summary["reason"] == "unsupported_extension", summary
        assert ".xyz" in summary["message"], summary

    def test_pdb_gz_reports_compressed_input(self, tmp_path):
        res, results = _run_load(tmp_path, {"system.pdb.gz": _MIN_GZ})
        if res.success:
            pytest.xfail("pdb.gz unexpectedly loaded")
        summary = results.get_data("loading/failure_summary")
        assert summary["reason"] == "compressed_input", summary
        assert ".gz" in summary["message"], summary


class TestEntLoadsAsPdb:
    def test_ent_loads_like_pdb(self, tmp_path):
        res, results = _run_load(tmp_path, {"model.ent": _MIN_PDB})
        assert res.success, res.attempts and [
            (a.strategy.value, a.error_message) for a in res.attempts]
        assert res.final_strategy.value == "pdb", res.final_strategy
