"""W3.1 item 11: bond stranded residue metals to their coordination
partners (un-pin the false heme-Fe ion, cytc B__v1).

Audit §3 item 11: the cytc e2e fixture run produced segment B__v1 — a
phantom "ion" segment that is the HEM residue's own iron. Root cause
(live evidence): the heme Fe-N coordination distance (~2.0 A) exceeds
the bond-guess fudge cutoff (vdW Fe+N ~3.05 A x 0.55 = 1.68 A), so the
Fe atom inside the multi-atom HEM residue ends up with ZERO bonds and
becomes its own connected component — the heme verifies as a Fe-free
porphyrin (C34H30N4O4) plus a bare Fe.

Fix: after bond guessing, a STRANDED metal atom (Fe/Zn/Mg/Mn/Cu/Ni/
Co/Mo/V/W) inside a MULTI-ATOM residue gets coordination bonds to its
same-residue N/O/S partners within 2.6 A. Free ions (single-atom
residues) are never touched — they are legitimately unbonded.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")
rdkit = pytest.importorskip("rdkit")

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "nucleic" / (
    "cytc_full.pdb")
C13 = Path("/home/tomsko/work/bat3_article_reviews/bioid_bughunt/"
           "testcases/C13_sodium_acetate/input")


def _repaired_universe(pdb_path: Path):
    from MDAnalysis import Universe
    from src_new.loader.repair import TopologyRepair
    from src_new.config.loader import RunConfig
    u = Universe(str(pdb_path), in_memory=True)
    cfg = RunConfig()
    cfg.loader.guess_missing_bonds = True  # the pipeline-run default
    repair = TopologyRepair(u, cfg)
    repair.run()
    return u, repair


class TestStrandedResidueMetals:
    def test_cytc_heme_fe_gets_coordination_bonds(self):
        """REAL fixture, real TopologyRepair: the HEM Fe (resid 105,
        multi-atom residue) must be bonded to its porphyrin N atoms —
        RED at HEAD: zero bonds, the Fe is its own component."""
        u, repair = _repaired_universe(FIXTURE)
        fe = [a for a in u.atoms if a.name == "FE"][0]
        idx_of = {int(a.index): a for a in u.atoms}
        partners = []
        for b in u.bonds:
            i, j = int(b.indices[0]), int(b.indices[1])
            if i == fe.index:
                partners.append(idx_of[j])
            elif j == fe.index:
                partners.append(idx_of[i])
        n_partners = [p for p in partners
                      if p.residue.resid == 105 and p.name in
                      ("NA", "NB", "NC", "ND")]
        assert n_partners, (
            f"the heme Fe must be bonded to its porphyrin N atoms; "
            f"FE bonds: {[(p.name, p.residue.resname) for p in partners]}")

    def test_cytc_e2e_heme_keeps_fe(self, tmp_path):
        """REAL fixture through the real executor (stages 0-5): no
        bare-Fe segment; the HEM segment carries Fe with its porphyrin
        nitrogens. RED at HEAD: segment B__v1 with molecular_formula
        'Fe'."""
        w31 = importlib.import_module(
            "tests.src_new.loader.test_chainless_topology_w31")
        import shutil
        src = tmp_path / "src"
        src.mkdir()
        shutil.copy(FIXTURE, src / "cytc.pdb")
        data = w31._run_results(src, tmp_path, input_kind="pdb")
        formulas = {}
        for seg, payload in (data.get("signatures") or {}).items():
            gen = (payload or {}).get("generated") or {}
            f = gen.get("molecular_formula")
            if f:
                formulas[seg] = str(f)
        assert formulas, "no formulas generated"
        bare = [s for s, f in formulas.items() if f.strip() == "Fe"]
        assert not bare, (
            f"the heme Fe must not be a separate segment: {formulas}")
        assert any("Fe" in f and "N" in f for f in formulas.values()), (
            f"the heme molecule must keep its Fe: {formulas}")

    def test_free_ions_stay_unbonded(self, tmp_path):
        """REAL corpus deposit (C13 sodium acetate) through the real
        executor: the free Na+ (single-atom residue) is NOT bonded to
        anything by the stranded-metal repair — it stays a proper ion
        segment. Guard (GREEN at HEAD)."""
        if not C13.is_dir():
            pytest.skip("corpus deposit not available")
        w31 = importlib.import_module(
            "tests.src_new.loader.test_chainless_topology_w31")
        data = w31._run_results(C13, tmp_path, input_kind="pdb")
        formulas = {}
        for seg, payload in (data.get("signatures") or {}).items():
            gen = (payload or {}).get("generated") or {}
            if gen.get("molecular_formula"):
                formulas[seg] = str(gen["molecular_formula"])
        assert any(f.strip() == "Na" for f in formulas.values()), (
            f"the free Na+ ion must remain its own segment: {formulas}")
