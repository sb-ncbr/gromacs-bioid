"""W3.1 S17 follow-up: intra-residue fragment completion (torn heme
propionate arms, S17 hemoglobin-as-GRO).

The W3.1 gate on the fresh offline sweep had exactly one per-case
expectation FAIL left: S17_hemoglobin_as_gro "heme C34FeN4O4 present".
Item 11 already moved the stranded Fe INTO the heme molecules; what
remains is that each HEM residue's two propionate arms (CGA/CGD + O1/O2)
tear off as separate CO2 fragments: the ring carbon - arm carbon bond
in this GRO is 2.09 A, beyond the 0.55 vdW-fudge cutoff (C+C 3.4 x
0.55 = 1.87 A), so the residue splits into a porphyrin plus two
carboxylate fragments.

Fix: complete_intra_residue_fragments — inside a multi-atom residue,
merge bond-connected components whose closest HEAVY-atom cross pair is
<= 2.5 A (not fitted to S17: the merge is intra-residue only and
non-bonded heavy-heavy contacts stay >= ~2.6-2.7 A even in short
H-bonds). Guards (user-approved):
  - water residues are never touched;
  - single-atom metal/ion components are never merged by this rule
    (bond_stranded_residue_metals owns residue metals; free ions are
    legitimately unbonded);
  - heavy atoms only;
  - distinct molecules sharing resname+resid (wrapped GRO numbering)
    are NOT merged: 2.7 A > cutoff stays split.
"""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path

import numpy as np
import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")
rdkit = pytest.importorskip("rdkit")

S17 = Path("/home/tomsko/work/bat3_article_reviews/bioid_bughunt/"
           "testcases/S17_hemoglobin_as_gro/input")
C13 = Path("/home/tomsko/work/bat3_article_reviews/bioid_bughunt/"
           "testcases/C13_sodium_acetate/input")


def _repaired_universe(path: Path, kind: str):
    from MDAnalysis import Universe
    from src_new.loader.repair import TopologyRepair
    from src_new.config.loader import RunConfig
    if kind == "gro":
        u = Universe(str(path), in_memory=True)
        u.guess_TopologyAttrs(context="default", to_guess=["elements"])
    else:
        u = Universe(str(path), in_memory=True)
    cfg = RunConfig()
    cfg.loader.guess_missing_bonds = True  # the pipeline-run default
    repair = TopologyRepair(u, cfg)
    repair.run()
    return u, repair


def _components(u, atom_indices):
    """Bond-connected components within the given atom index set."""
    idx_set = set(int(i) for i in atom_indices)
    parent = {i: i for i in idx_set}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for b in u.bonds:
        i, j = int(b.indices[0]), int(b.indices[1])
        if i in idx_set and j in idx_set:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj
    comps = {}
    for i in idx_set:
        comps.setdefault(find(i), []).append(i)
    return list(comps.values())


def _synthetic_pdb(tmp_path: Path, rows) -> Path:
    """Fixed-column PDB writer; rows = (name, resname, resid, xyz)."""
    def element(name: str) -> str:
        # two-letter symbols (NA, FE, ...) must reach the element column
        # intact — name[0] would turn sodium into nitrogen
        if len(name) >= 2 and name[1].isalpha():
            return name[:2].upper()
        return name[0].upper()

    lines = []
    for k, (name, resname, resid, xyz) in enumerate(rows):
        x, y, z = xyz
        lines.append(
            f"ATOM  {k + 1:5d} {name:>4s} {resname:>3s} A{resid:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          "
            f"{element(name):>2s}  \n")
    p = tmp_path / "synth.pdb"
    p.write_text("".join(lines))
    return p


class TestIntraResidueCompletion:
    def test_s17_heme_arms_rejoin(self):
        """REAL S17 GRO, real TopologyRepair with guessed bonds: each
        HEM residue (43 atoms) must be ONE connected component —
        RED at HEAD: ring + CGA arm + CGD arm (+ pre-item-11 FE)."""
        u, repair = _repaired_universe(S17 / "4HHB.gro", "gro")
        hems = [r for r in u.residues if r.resname == "HEM"]
        assert len(hems) == 4
        for r in hems:
            comps = _components(u, r.atoms.indices)
            assert len(comps) == 1, (
                f"HEM {r.resid} torn into {len(comps)} components: "
                f"{[[u.atoms[i].name for i in c] for c in comps]}")

    def test_report_counts_completion_bonds(self):
        u, repair = _repaired_universe(S17 / "4HHB.gro", "gro")
        # 4 hemes x 2 arms -> 8 rejoined arms (item 11 already owns FE).
        assert repair.report.intra_residue_bonds >= 8

    def test_single_atom_ion_component_not_merged(self, tmp_path):
        """Guard: a single-atom metal/ion component inside a multi-atom
        residue at 2.2 A from a carboxylate O — beyond the covalent fudge
        cutoff (~2.09 A for Na-O) but within the completion cutoff —
        must NOT be merged by completion (ions stay ions)."""
        p = _synthetic_pdb(tmp_path, [
            # acetate-ish residue 1 (C-C and C=O within fudge cutoffs)
            ("C1", "ACY", 1, (0.0, 0.0, 0.0)),
            ("C2", "ACY", 1, (1.5, 0.0, 0.0)),
            ("O1", "ACY", 1, (2.0, 1.2, 0.0)),
            ("O2", "ACY", 1, (2.0, -1.2, 0.0)),
            # Na in the SAME residue, 2.2 A from O1: fudge cutoff for
            # Na-O is (2.27 + 1.52) * 0.55 = 2.09 A -> not covalently
            # bonded by the guesser; completion (<= 2.5 A) must refuse.
            ("NA", "ACY", 1, (2.0, 3.4, 0.0)),
        ])
        u, repair = _repaired_universe(p, "pdb")
        na = [a for a in u.atoms if a.name == "NA"][0]
        comps = _components(u, range(len(u.atoms)))
        na_comp = [c for c in comps if int(na.index) in c]
        assert len(na_comp[0]) == 1, (
            "the single-atom ion component must not be merged by "
            "intra-residue completion")

    def test_water_residues_never_merged(self, tmp_path):
        """Guard: water residues are skipped entirely — an O 2.0 A from
        the water's O (beyond the O-O fudge cutoff 1.67 A, within the
        completion cutoff) in a SOL residue stays a separate component."""
        p = _synthetic_pdb(tmp_path, [
            ("O", "SOL", 1, (0.0, 0.0, 0.0)),
            ("O", "SOL", 1, (2.0, 0.0, 0.0)),
        ])
        u, repair = _repaired_universe(p, "pdb")
        assert len(_components(u, range(len(u.atoms)))) == 2

    def test_shared_resid_molecules_not_merged(self, tmp_path):
        """Negative test (user-required): two DISTINCT molecules sharing
        resname+resid (wrapped GRO numbering collapses them into one
        MDAnalysis residue) 2.7 A apart must stay separate components —
        non-bonded heavy-heavy contacts start at ~2.6-2.7 A and the
        cutoff must not bridge them."""
        lines = ["shared-resid synthetic", "    4"]
        # GRO coordinates are NANOMETRES: 0.150 nm = 1.5 A etc.
        rows = [
            (1, "MOL", "C1", 1, (0.0, 0.0, 0.0)),
            (1, "MOL", "C2", 2, (0.150, 0.0, 0.0)),
            # same resid+resname: one MDAnalysis residue, but a second
            # molecule; nearest cross pair C2-C3 = 2.7 A (0.270 nm)
            (1, "MOL", "C3", 3, (0.420, 0.0, 0.0)),
            (1, "MOL", "C4", 4, (0.570, 0.0, 0.0)),
        ]
        for resid, resname, name, nr, (x, y, z) in rows:
            lines.append(
                f"{resid:5d}{resname:<5s}{name:>5s}{nr:5d}"
                f"{x:8.3f}{y:8.3f}{z:8.3f}")
        lines.append("   3.00000   3.00000   3.00000")
        p = tmp_path / "shared.gro"
        p.write_text("\n".join(lines) + "\n")
        u, repair = _repaired_universe(p, "gro")
        assert len(u.residues) == 1, (
            "precondition: same resid+resname must be ONE residue")
        comps = _components(u, range(len(u.atoms)))
        assert len(comps) == 2, (
            "two molecules 2.7 A apart must not be merged")
        assert repair.report.intra_residue_bonds == 0

    def test_c13_sodium_acetate_e2e_unchanged(self, tmp_path):
        """REAL C13 corpus case through stages 0-5: the Na+ stays a
        free ion segment and the acetate keeps C2H3O2 — the completion
        must not bond contact ion pairs."""
        w31 = importlib.import_module(
            "tests.src_new.loader.test_chainless_topology_w31")
        data = w31._run_results(C13, tmp_path, input_kind="gro")
        segs = data.get("signatures") or {}
        formulas = sorted(
            (p or {}).get("generated", {}).get("molecular_formula")
            for p in segs.values())
        assert "Na" in formulas, f"Na+ ion segment missing: {formulas}"
        assert "C2H3O2" in formulas, f"acetate changed: {formulas}"

    def test_s17_e2e_gate_formula(self, tmp_path):
        """REAL S17 GRO through stages 0-5 (the gate's own expectation):
        a heme segment with molecular_formula_heavy C34FeN4O4 —
        RED at HEAD: torn arms (C33FeN4O2 / C32FeN4 + CO2 fragments)."""
        w31 = importlib.import_module(
            "tests.src_new.loader.test_chainless_topology_w31")
        src = tmp_path / "src"
        src.mkdir()
        shutil.copy(S17 / "4HHB.gro", src / "4HHB.gro")
        data = w31._run_results(src, tmp_path, input_kind="gro")
        segs = data.get("signatures") or {}
        heavies = [(p or {}).get("generated", {}).get("molecular_formula_heavy")
                   for p in segs.values()]
        assert "C34FeN4O4" in heavies, (
            f"heme C34FeN4O4 missing from S17 segments: {heavies}")
