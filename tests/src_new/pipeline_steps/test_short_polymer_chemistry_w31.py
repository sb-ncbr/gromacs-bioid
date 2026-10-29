"""W3.1 item 6 (B1): chemistry for short polymer-typed segments.

Audit §3 item 6: the W3 B1 suppression (polymer-typed segments never
run smiles/selfies/inchi_key chemistry) also hit short peptides and
single amino acids TYPED as polymer — a ligand glycine zwitterion (C19)
got no InChIKey at all. Chemistry is kept for polymer-typed segments
with <= 5 residues; real polymers stay suppressed.

Acceptance (audit): C19 InChIKey present — pinned end to end on the
real corpus deposit below.
"""

from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path

import pytest

MDAnalysis = pytest.importorskip("MDAnalysis")
pytest.importorskip("rdkit")

CASE = Path("/home/tomsko/work/bat3_article_reviews/bioid_bughunt/"
            "testcases/C19_glycine_zwitterion/input")


class TestShortPolymerKeepsChemistry:
    def test_c19_glycine_gets_inchikey(self, tmp_path):
        """REAL corpus deposit, real executor, stages 0-5: the glycine
        zwitterion (typed polymer — it IS an amino acid) must carry an
        InChIKey signature (RED at HEAD: suppressed by B1)."""
        if not CASE.is_dir():
            pytest.skip("corpus deposit not available")
        w31 = importlib.import_module(
            "tests.src_new.loader.test_chainless_topology_w31")
        data = w31._run_results(CASE, tmp_path)
        sigs = data.get("signatures") or {}
        assert sigs, "no signatures generated for C19"
        chem_keys = set()
        for seg, payload in sigs.items():
            gen = (payload or {}).get("generated") or {}
            chem_keys |= {k for k in gen if k.startswith("inchi_key")}
        assert chem_keys, (
            f"C19 must carry an InChIKey signature (short polymer "
            f"chemistry): segments={list(sigs)}")

    def test_suppression_policy_by_residue_count(self):
        """Unit pin of the policy: <=5-residue polymer keeps chemistry;
        >5-residue polymer stays suppressed; non-polymer unaffected."""
        from src_new.pipeline_steps import _polymer_chemistry_suppressed
        from src_new.molecules.instances import MoleculeInstance, MoleculeType

        def _inst(mtype, resids):
            return MoleculeInstance(
                instance_id="i", molecule_type=MoleculeType(mtype),
                resids=list(resids), atom_count=10)

        glycine = _inst(MoleculeType.PROTEIN, [1])
        penta = _inst(MoleculeType.PROTEIN, [1, 2, 3, 4, 5])
        hexa = _inst(MoleculeType.PROTEIN, [1, 2, 3, 4, 5, 6])
        ligand = _inst(MoleculeType.SMALL_MOLECULE, [1])

        for gen in ("smiles", "selfies", "inchi_key"):
            assert not _polymer_chemistry_suppressed(glycine, gen), (
                "1-residue polymer (amino-acid ligand) keeps chemistry")
            assert not _polymer_chemistry_suppressed(penta, gen), (
                "5-residue polymer keeps chemistry")
            assert _polymer_chemistry_suppressed(hexa, gen), (
                "6-residue polymer stays suppressed")
            assert not _polymer_chemistry_suppressed(ligand, gen)
