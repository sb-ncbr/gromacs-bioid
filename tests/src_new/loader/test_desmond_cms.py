"""dm1 audit (L6): Desmond .cms systems load with BioID's own Maestro reader
(31 .cms deposits in the generalist index; 7 had nothing else). Checked on
a real Desmond POPC/SPC membrane (zenodo/10948670, 31,300 atoms) during
development: POPC came out as PC(16:0/18:1(9Z)); the fixture below has the
same layout (full_system ct, then one ct per component)."""
import shutil
from pathlib import Path

import pytest

pytest.importorskip("MDAnalysis")

from tests.src_new.loader.test_chainless_topology_w31 import _run_results  # noqa: E402

CMS = '''{
 s_m_m2io_version
 :::
 2.0.0
}

f_m_ct {
 s_m_title
 r_chorus_box_ax
 r_chorus_box_ay
 r_chorus_box_az
 r_chorus_box_bx
 r_chorus_box_by
 r_chorus_box_bz
 r_chorus_box_cx
 r_chorus_box_cy
 r_chorus_box_cz
 s_ffio_ct_type
 :::
 "ethanol in \\"water\\""
 30.0 0 0 0 30.0 0 0 0 30.0
 full_system
 m_atom[12] {
  # First column is atom index #
  i_m_mmod_type
  r_m_x_coord
  r_m_y_coord
  r_m_z_coord
  i_m_residue_number
  s_m_pdb_residue_name
  i_m_atomic_number
  s_m_pdb_atom_name
  s_m_chain_name
  :::
  1 3 10.000 10.000 10.000 1 "EOH " 6 " C1 " <>
  2 3 11.520 10.000 10.000 1 "EOH " 6 " C2 " <>
  3 23 12.000 11.350 10.000 1 "EOH " 8 " O  " <>
  4 41 9.640 10.510 10.890 1 "EOH " 1 " H11" <>
  5 41 9.640 10.510 9.110 1 "EOH " 1 " H12" <>
  6 41 9.640 8.980 10.000 1 "EOH " 1 " H13" <>
  7 41 11.880 9.490 10.890 1 "EOH " 1 " H21" <>
  8 41 11.880 9.490 9.110 1 "EOH " 1 " H22" <>
  9 42 12.960 11.350 10.000 1 "EOH " 1 " HO " <>
  10 16 20.000 20.000 20.000 2 SPC 8 " OW " W
  11 42 20.960 20.000 20.000 2 SPC 1 " HW1" W
  12 42 19.760 20.930 20.000 2 SPC 1 " HW2" W
  :::
 }
 m_bond[11] {
  # First column is bond index #
  i_m_from
  i_m_to
  i_m_order
  :::
  1 1 2 1
  2 2 3 1
  3 1 4 1
  4 1 5 1
  5 1 6 1
  6 2 7 1
  7 2 8 1
  8 3 9 1
  9 10 11 1
  10 10 12 1
  11 2 1 1
  :::
 }
}

f_m_ct {
 s_m_title
 s_ffio_ct_type
 :::
 water
 solvent
 m_atom[3] {
  r_m_x_coord
  r_m_y_coord
  r_m_z_coord
  i_m_atomic_number
  :::
  1 20.0 20.0 20.0 8
  2 20.96 20.0 20.0 1
  3 19.76 20.93 20.0 1
  :::
 }
}
'''


def test_reader_uses_full_system(tmp_path):
    from src_new.loader.desmond_cms import cms_universe
    p = tmp_path / "sys.cms"
    p.write_text(CMS)
    u = cms_universe(p)
    assert u.atoms.n_atoms == 12              # component ct not added twice
    assert len(u.bonds) == 10                 # duplicate 2-1 bond merged
    assert list(u.residues.resnames) == ["EOH", "SPC"]
    assert [s.segid for s in u.segments] == ["C0", "W"]
    assert list(u.atoms.names[:3]) == ["C1", "C2", "O"]
    assert list(u.dimensions) == [30, 30, 30, 90, 90, 90]


def test_cms_pipeline_identifies_ethanol(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "sys.cms").write_text(CMS)
    data = _run_results(case, tmp_path / "run")
    ok = [a for a in data["loading"]["attempts"] if a.get("status") == "success"]
    assert ok[-1]["strategy"] == "desmond_cms"
    formulas = {v["generated"].get("molecular_formula") for v in data["signatures"].values()}
    assert {"C2H6O", "H2O"} <= formulas, formulas


def test_malformed_cms_is_a_format_error(tmp_path):
    from src_new.loader.desmond_cms import CmsFormatError, read_cms
    p = tmp_path / "bad.cms"
    p.write_text("f_m_ct { s_m_title ::: x m_atom[2] { r_m_x_coord ::: 1 0.0 ::: } }")
    with pytest.raises(CmsFormatError):
        read_cms(p)
