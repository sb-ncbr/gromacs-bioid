"""W3.1 item 1 (A8 x facade, F2): chain-less topologies must not collapse
into one segment, and the broken-chain union must never merge distinct
molecules.

Production regression (reviewer audit of 48be27553..fe18ac7f6, confirmed
in the agent's own offline_w3 sweep):
- M01 AMBER prmtop (segid SYSTEM): 4 correct segments -> ONE lipid-typed
  segment with 0 FASTA keys.
- M05 nucleosome: 10 segments -> 1 lipid + Zn.
- M07 RNA duplex: 2 strands -> 1.
Root cause: A2's F2 union accepted any set of polymer fragments with
unique (resid, icode); AMBER numbers residues continuously across
chains, so 4 separate chains passed as "one broken chain". Additionally
the A-09 representative unioned ALL polymer fragments of a segment.

Acceptance (mechanical, per the audit):
- M01: >= 2 protein + >= 2 nucleic chain copies;
- M05: >= 8 protein + >= 2 nucleic chain copies;
- M07: 2 RNA strands;
- synthetic: 2 chains in one segid with continuous numbering -> 2
  segments; identical homo-oligomers -> 1 segment with copies == 2
  (never collapsed to molecule_count 1).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not pytest.importorskip("MDAnalysis") or not pytest.importorskip("rdkit"),
    reason="pipeline e2e needs MDAnalysis + rdkit",
)

CORPUS = Path(
    "/home/tomsko/work/bat3_article_reviews/bioid_bughunt/testcases")


def _stage_steps():
    from src_new.pipeline_steps import build_load_and_export_tasks
    return build_load_and_export_tasks()[:6]  # 0-5: hermetic stages


def _run_results(case_dir: Path, tmp_path: Path) -> dict:
    """Run stages 0-5 on a corpus deposit; return the results data."""
    from src_new.executor.executor import PipelineExecutor
    from src_new.results.results_manager import ResultsManager

    assert case_dir.is_dir(), f"corpus deposit missing: {case_dir}"
    work = tmp_path / "input"
    shutil.copytree(case_dir, work)
    results_path = tmp_path / "results.json"
    manager = ResultsManager(str(results_path), pipeline_name="w31")
    executor = PipelineExecutor(steps=_stage_steps(),
                                results_manager=manager,
                                pipeline_name="w31")
    executor.run(working_directory=work,
                 output_directory=tmp_path / "out",
                 input_kind="pdb",
                 input_files={p.name: p for p in work.iterdir()})
    payload = json.loads(results_path.read_text())
    assert payload["pipeline"]["status"] == "success", (
        payload.get("critical_errors"))
    return payload.get("data", {})


def _type_copies(data: dict) -> dict:
    """Sum molecule copies per polymer class over all segments
    (mirrors structural_gate's _type_copies)."""
    segs = (data.get("universe", {}) or {}).get("segments", {}) or {}
    out = {"protein": 0, "nucleic": 0}
    for meta in segs.values():
        props = meta.get("properties") or {}
        copies = int(props.get("molecule_count") or 1)
        if props.get("is_protein"):
            out["protein"] += copies
        if props.get("is_nucleic"):
            out["nucleic"] += copies
    return out


class TestChainlessTopologyRealDeposits:
    def test_m01_protein_dna_chains_split(self, tmp_path):
        data = _run_results(CORPUS / "M01_1p71_protein_dna_amber" / "input",
                            tmp_path)
        c = _type_copies(data)
        assert c["protein"] >= 2, f"M01 protein copies collapsed: {c}"
        assert c["nucleic"] >= 2, f"M01 DNA strands collapsed: {c}"

    def test_m05_nucleosome_chains_split(self, tmp_path):
        data = _run_results(CORPUS / "M05_nucleosome_ligand_amber" / "input",
                            tmp_path)
        c = _type_copies(data)
        assert c["protein"] >= 8, f"M05 histone copies collapsed: {c}"
        assert c["nucleic"] >= 2, f"M05 DNA strands collapsed: {c}"

    def test_m07_rna_duplex_two_strands(self, tmp_path):
        data = _run_results(CORPUS / "M07_rna_2l8f_amber" / "input",
                            tmp_path)
        c = _type_copies(data)
        assert c["nucleic"] >= 2, f"M07 RNA strands collapsed: {c}"


class TestBrokenChainUnionGuards:
    """Species-aware union: copies and distinct molecules are never
    unioned into one chimera chain (F2 accepts only pieces of ONE chain)."""

    def _duplex_universe(self, chain_a=3, chain_b=3, same_sequence=False):
        import MDAnalysis as mda
        import numpy as np
        res_a = ["ALA", "GLY", "LYS"][:chain_a]
        res_b = res_a if same_sequence else ["SER", "VAL", "THR"][:chain_b]
        names = {"ALA": "CA", "GLY": "CA", "LYS": "CA",
                 "SER": "CA", "VAL": "CA", "THR": "CA"}
        all_res = res_a + res_b
        n = len(all_res)
        u = mda.Universe.empty(n, n_residues=n, atom_resindex=list(range(n)),
                               trajectory=True)
        u.add_TopologyAttr("resnames", all_res)
        u.add_TopologyAttr("resids", list(range(1, n + 1)))  # continuous!
        u.add_TopologyAttr("segids", ["SYSTEM"] * 1)
        u.add_TopologyAttr("names", [names[r] for r in all_res])
        u.add_TopologyAttr("elements", ["C"] * n)
        u.add_TopologyAttr("chainIDs", ["A"] * len(res_a) + ["B"] * len(res_b))
        bonds = [(i, i + 1) for i in range(0, len(res_a) - 1)]
        bonds += [(i, i + 1) for i in range(len(res_a), n - 1)]
        u.add_TopologyAttr("bonds", bonds)
        u.atoms.positions = np.arange(n * 3, dtype=float).reshape(n, 3) * 4.0
        return u

    def _segments(self, u):
        from src_new.loader.universe_facade import LoadedUniverse
        fac = LoadedUniverse(universe=u, decision=None, repair_report=None,
                             results=None, enhanced_nucleic_recognition=False)
        segs = {}
        for name in sorted(fac.get_segments()):
            p = fac.get_segment_properties(name)
            segs[name] = {
                "copies": p.molecule_count,
                "atoms": p.atom_count_fragment,
                "protein": p.flags.is_protein if hasattr(p.flags, "is_protein") else None,
            }
        return segs

    def test_two_distinct_chains_one_segid_give_two_segments(self):
        u = self._duplex_universe(same_sequence=False)
        segs = self._segments(u)
        assert len(segs) == 2, f"expected 2 segments (rep + virtual), got {segs}"

    def test_identical_copies_not_unioned_to_one_molecule(self):
        u = self._duplex_universe(same_sequence=True)
        segs = self._segments(u)
        total_copies = sum(s["copies"] or 1 for s in segs.values())
        assert len(segs) == 1, f"identical copies should be one segment, got {segs}"
        assert total_copies == 2, f"homo-oligomer must not collapse to 1: {segs}"
