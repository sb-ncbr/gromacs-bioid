"""mdval audit item 6c (2026-11-21): a PDB with SOME chain IDs blank loads
those atoms into segment '' (MDAnalysis names the segment 'SYSTEM' only when
every chain ID is blank). Biopython's mmCIF writer crashed on the empty
chain id ("string index out of range", figshare 24161301, 22182562, zenodo
10696770, figshare 30226180): no system mmCIF, no selectors, and a segment
file named '.mmcif'. Repair names the blank segment; the export survives an
empty segid anyway."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("MDAnalysis")
pytest.importorskip("Bio")
from MDAnalysis import Universe

from src_new.config.loader import RunConfig
from src_new.loader.export_mmcif import (
    _build_biopython_structure, export_segment_mmcif, export_system_mmcif)
from src_new.loader.repair import TopologyRepair
from src_new.loader.universe_facade import LoadedUniverse

_PDB = """\
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       2.009   1.420   0.000  1.00  0.00           C
ATOM      4  O   ALA A   1       1.251   2.390   0.000  1.00  0.00           O
HETATM    5  O   HOH     2       8.000   8.000   8.000  1.00  0.00           O
HETATM    6  O   HOH     3      12.000   8.000   8.000  1.00  0.00           O
END
"""


def _blank_chain_universe(tmp_path, text=_PDB):
    pdb = tmp_path / "blank.pdb"
    pdb.write_text(text)
    return Universe(str(pdb))


def _facade(u):
    return LoadedUniverse(universe=u, decision=SimpleNamespace(),
                          repair_report=SimpleNamespace(), results=None)


def test_mdanalysis_gives_blank_chain_atoms_an_empty_segid(tmp_path):
    u = _blank_chain_universe(tmp_path)
    assert sorted(u.segments.segids) == ["", "A"]


def test_repair_names_the_blank_segment(tmp_path):
    u = _blank_chain_universe(tmp_path)
    report = TopologyRepair(u, RunConfig()).run()
    assert sorted(u.segments.segids) == ["A", "SYSTEM"]
    assert report.blank_segid_atoms == 2
    assert report.segids_named == "SYSTEM"
    assert sorted(_facade(u).get_segments()) == ["A", "SYSTEM"]


def test_repair_picks_an_unused_label():
    u = Universe.empty(3, n_residues=2, n_segments=2, atom_resindex=[0, 0, 1],
                       residue_segindex=[0, 1], trajectory=True)
    u.add_TopologyAttr("names", ["C1", "O1", "OW"])
    u.add_TopologyAttr("resnames", ["LIG", "HOH"])
    u.add_TopologyAttr("segids", ["SYSTEM", ""])
    TopologyRepair(u, RunConfig())._name_blank_segids()
    assert list(u.segments.segids) == ["SYSTEM", "SYSTEM_1"]


def test_all_blank_pdb_keeps_mdanalysis_system(tmp_path):
    u = _blank_chain_universe(tmp_path, _PDB.replace("ALA A", "ALA  "))
    report = TopologyRepair(u, RunConfig()).run()
    assert list(u.segments.segids) == ["SYSTEM"]
    assert report.blank_segid_atoms == 0


def test_export_survives_an_empty_segid(tmp_path):
    """Without the repair step (segid '' left in place) the whole-system
    export and selectors still work; the blank chain is written as SYSTEM."""
    u = _blank_chain_universe(tmp_path)
    facade = _facade(u)
    structure = _build_biopython_structure(u)
    assert sorted(c.id for c in structure[0]) == ["A", "SYSTEM"]

    from src_new.results.results_manager import ResultsManager
    results = ResultsManager(tmp_path / "results.json")
    out = export_system_mmcif(facade, tmp_path / "system.mmcif", results)
    text = out.read_text()
    assert "SYSTEM" in text
    selectors = results.get_data("render/segment_selectors")
    blank = [v for k, v in selectors.items() if not k or k.startswith("__v")]
    assert blank and all(v["chains"] == ["SYSTEM"] for v in blank)
    assert sum(v["atom_count"] for v in blank) == 2
    seg = export_segment_mmcif(facade, "", tmp_path / "blank.mmcif")
    assert seg.exists()


def test_export_after_repair(tmp_path):
    u = _blank_chain_universe(tmp_path)
    TopologyRepair(u, RunConfig()).run()
    facade = _facade(u)
    from src_new.results.results_manager import ResultsManager
    results = ResultsManager(tmp_path / "results.json")
    export_system_mmcif(facade, tmp_path / "system.mmcif", results)
    selectors = results.get_data("render/segment_selectors")
    assert selectors["SYSTEM"]["chains"] == ["SYSTEM"]
    assert selectors["A"]["chains"] == ["A"]
    for seg in facade.get_segments():
        assert seg  # never a segment file named '.mmcif'
        assert export_segment_mmcif(facade, seg, tmp_path / f"{seg}.mmcif").exists()
