"""W3.1 item 7 (B4): cut only CONECT-origin metal bonds, not topology
bonds.

Audit §2 B4 hazard (live evidence): the W3 coordination cut also
removed FORCE-FIELD topology bonds — M14's FE2P complexes (CHARMM TPR:
six single-atom FE2P residues, each bonded to six porphyrin N atoms of
a LIG residue, MCPB-style) came out as a Fe-free porphyrin plus a
stray Fe ion segment (molecular_formula == "Fe").

Fix contract: the cut applies only to structure-authored bonds (PDB /
mmCIF loads, where CONECT records and distance guessing are the only
bond sources). Topology-backed loads (GROMACS/AMBER/CHARMM/LAMMPS)
carry parametrization-authored bonds and are never cut.

Acceptance (audit §3 item 7): the M14 complex is unchanged (no bare-Fe
segment, the heme segment keeps its Fe); an MCPB heme probe keeps Fe.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")

M14 = Path("/home/tomsko/work/bat3_article_reviews/bioid_bughunt/"
           "testcases/M14_lipid_bilayer_charmm_tpr/input")


def _write_probe(dir_path: Path) -> Path:
    """Write a REAL GROMACS top+itp+gro MCPB-style heme probe: a
    single-atom FE residue covalently bonded (topology [ bonds ]) to
    the four porphyrin N atoms of a HEM residue."""
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "heme.itp").write_text(
        "[ moleculetype ]\n"
        "; name  nrexcl\n"
        "HEME    3\n"
        "\n"
        "[ atoms ]\n"
        ";  nr  type  resnr residue  atom  cgnr  charge    mass\n"
        "     1   NP      1    HEM     NA     1    0.00  14.0067\n"
        "     2   NP      1    HEM     NB     1    0.00  14.0067\n"
        "     3   NP      1    HEM     NC     1    0.00  14.0067\n"
        "     4   NP      1    HEM     ND     1    0.00  14.0067\n"
        "     5   CT      1    HEM     CM1    1    0.00  12.0110\n"
        "     6   CT      1    HEM     CM2    1    0.00  12.0110\n"
        "     7   FE      2    FE      FE     2    2.00  55.8450\n"
        "\n"
        "[ bonds ]\n"
        ";  ai  aj  funct\n"
        "      1   5     1\n"
        "      2   5     1\n"
        "      3   6     1\n"
        "      4   6     1\n"
        "      1   7     1\n"
        "      2   7     1\n"
        "      3   7     1\n"
        "      4   7     1\n")
    (dir_path / "heme.top").write_text(
        '#include "heme.itp"\n'
        "\n"
        "[ system ]\n"
        "MCPB-style heme probe (single-atom FE residue, topology bonds "
        "to porphyrin N)\n"
        "\n"
        "[ molecules ]\n"
        "HEME 1\n")
    atoms = [("HEM", "NA", 1), ("HEM", "NB", 2), ("HEM", "NC", 3),
             ("HEM", "ND", 4), ("HEM", "CM1", 5), ("HEM", "CM2", 6),
             ("FE", "FE", 7)]
    coords = [(0.1, 0.1, 0.1), (-0.1, 0.1, 0.1), (0.1, -0.1, 0.1),
              (-0.1, -0.1, 0.1), (0.3, 0.3, 0.1), (-0.3, -0.3, 0.1),
              (0.0, 0.0, 0.1)]
    lines = ["MCPB-style heme probe", f"{len(atoms):5d}"]
    for i, ((res, name, num), (x, y, z)) in enumerate(
            zip(atoms, coords), start=1):
        lines.append(f"{i:5d}{res:<5s}{name:>5s}{num:5d}"
                     f"{x:8.3f}{y:8.3f}{z:8.3f}")
    lines.append("{:>10}{:>10}{:>10}".format(2.0, 2.0, 2.0))
    (dir_path / "heme.gro").write_text("\n".join(lines) + "\n")
    return dir_path


def _formulas(data: dict) -> dict[str, str]:
    """segment -> molecular_formula from a stages-0-5 run's data."""
    out: dict[str, str] = {}
    for seg, payload in (data.get("signatures") or {}).items():
        gen = (payload or {}).get("generated") or {}
        f = gen.get("molecular_formula") or gen.get(
            "molecular_formula_heavy")
        if f:
            out[seg] = str(f)
    return out


class TestTopologyMetalBondsKept:
    def test_mcpb_probe_keeps_fe(self, tmp_path):
        """REAL GROMACS files through the real loader + facade: the FE
        stays bonded to the HEM residue (one molecule, formula contains
        Fe together with N). RED at HEAD: the cut splits a bare-Fe
        segment out of the heme."""
        w31 = importlib.import_module(
            "tests.src_new.loader.test_chainless_topology_w31")
        probe_dir = tmp_path / "probe"
        _write_probe(probe_dir)
        data = w31._run_results(probe_dir, tmp_path, input_kind="gromacs")
        formulas = _formulas(data)
        assert formulas, f"no formulas in run: {list(data)}"
        bare = [s for s, f in formulas.items() if f.strip() == "Fe"]
        assert not bare, (
            f"the coordination cut split a bare Fe segment out of the "
            f"MCPB heme: {formulas}")
        joined = [f for f in formulas.values() if "Fe" in f and "N" in f]
        assert joined, (
            f"the heme molecule must keep its Fe: {formulas}")

    def test_m14_complex_unchanged(self, tmp_path):
        """REAL corpus deposit (CHARMM TPR), real executor stages 0-5:
        the six FE2P complexes stay whole — no segment with formula
        'Fe', and heme segments keep Fe with their porphyrin atoms.
        RED at HEAD: seg_0_Title__v4 carried molecular_formula == 'Fe'."""
        if not M14.is_dir():
            pytest.skip("corpus deposit not available")
        w31 = importlib.import_module(
            "tests.src_new.loader.test_chainless_topology_w31")
        data = w31._run_results(M14, tmp_path)
        formulas = _formulas(data)
        assert formulas, "no formulas in M14 run"
        bare = [s for s, f in formulas.items() if f.strip() == "Fe"]
        assert not bare, (
            f"FE2P complexes were split (bare Fe segments): {formulas}")
        assert any("Fe" in f and "N" in f for f in formulas.values()), (
            f"heme segments must keep their Fe: {formulas}")

    def test_coordination_cut_gate_by_input_kind(self):
        """The gate: PDB/mmCIF (structure-authored bonds) keep the cut;
        topology-backed input kinds never cut; unknown provenance keeps
        the W3 status quo (the existing B4 pins ride on it)."""
        from src_new.loader.universe_facade import LoadedUniverse
        from src_new.input.models import LoadDecision, InputKind

        def _facade(kind):
            f = LoadedUniverse.__new__(LoadedUniverse)
            f.decision = LoadDecision(
                input_kind=kind, selected_strategy="x")
            return f

        assert LoadedUniverse._coordination_cut_enabled(
            _facade(InputKind.PDB)) is True
        assert LoadedUniverse._coordination_cut_enabled(
            _facade(InputKind.MMCIF)) is True
        for kind in (InputKind.GROMACS, InputKind.AMBER, InputKind.CHARMM,
                     InputKind.LAMMPS):
            assert LoadedUniverse._coordination_cut_enabled(
                _facade(kind)) is False, kind
        assert LoadedUniverse._coordination_cut_enabled(
            _facade(None)) is True  # unknown provenance: status quo
