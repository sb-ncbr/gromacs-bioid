"""W3 B4 (BH-002 subset): a single-atom HETATM ion inside a polymer
chain's segid must be split into its own ion segment.

Production evidence (g0a2091-1028):
- P10/S02 4WKQ: Na (HETATM A1102) absorbed into protein chain A.
- P04/S20 3PTB: Ca absorbed into the trypsin chain.

A2's F1 fix made segmentation use intra-segment components, so the
(unbonded) ion must now become its own (virtual or flat) fragment; this
file pins the behavior end-to-end on the real corpus deposits (stages
0-5: discovery .. generate_signatures — hermetic, no databases) plus a
synthetic minimal deposit.

Gate acceptance: no "CHECK BH-002" lines; P04 Ca and P10 Na are ion
segments.
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


def _run_segments(case_dir: Path, tmp_path: Path) -> tuple[dict, dict]:
    """Run stages 0-5 on a corpus deposit; return (segments, signatures)."""
    from src_new.executor.executor import PipelineExecutor
    from src_new.results.results_manager import ResultsManager

    assert case_dir.is_dir(), f"corpus deposit missing: {case_dir}"
    work = tmp_path / "input"
    shutil.copytree(case_dir, work)
    results_path = tmp_path / "results.json"
    manager = ResultsManager(str(results_path), pipeline_name="b4")
    executor = PipelineExecutor(steps=_stage_steps(),
                                results_manager=manager,
                                pipeline_name="b4")
    executor.run(working_directory=work,
                 output_directory=tmp_path / "out",
                 input_kind="pdb",
                 input_files={p.name: p for p in work.iterdir()})
    payload = json.loads(results_path.read_text())
    assert payload["pipeline"]["status"] == "success", (
        payload.get("critical_errors"))
    data = payload.get("data", {})
    return data.get("universe", {}).get("segments", {}) or {}, \
        data.get("signatures", {}) or {}


def _ion_segments(segments: dict, signatures: dict) -> dict:
    """Map segment name -> element for single-atom, non-polymer segments."""
    out = {}
    for name, meta in segments.items():
        props = meta.get("properties", {}) or {}
        if (props.get("atom_count_fragment") == 1
                and not props.get("is_protein")
                and not props.get("is_nucleic")):
            atom_sig = ((signatures.get(name, {}) or {})
                        .get("generated", {}) or {}).get("atom")
            out[name] = atom_sig
    return out


class TestAbsorbedIonSplits:
    def test_p10_4wkq_sodium_is_own_ion_segment(self, tmp_path):
        segments, signatures = _run_segments(
            CORPUS / "P10_4wkq_egfr_gefitinib" / "input", tmp_path)
        assert segments, "no segments produced"
        ions = _ion_segments(segments, signatures)
        assert any(v and str(v).strip().lower().startswith("na")
                   for v in ions.values()), (
            f"Na (HETATM A1102) must be its own ion segment; "
            f"single-atom segments found: {ions}")

    def test_p04_3ptb_calcium_is_own_ion_segment(self, tmp_path):
        segments, signatures = _run_segments(
            CORPUS / "P04_3ptb_trypsin_benzamidine" / "input", tmp_path)
        assert segments, "no segments produced"
        ions = _ion_segments(segments, signatures)
        assert any(v and str(v).strip().lower() == "ca"
                   for v in ions.values()), (
            f"Ca ion must be its own ion segment; "
            f"single-atom segments found: {ions}")


class TestSyntheticAbsorbedIon:
    def test_chain_absorbed_na_splits_in_fixture(self, tmp_path):
        """Minimal synthetic: 2 ALA residues + one Na HETATM, all under
        segid A — the Na must leave chain A."""
        pdb_text = (
            "ATOM      1  N   ALA A   1      11.104   6.134  10.000"
            "  1.00 20.00           N\n"
            "ATOM      2  CA  ALA A   1      12.560   6.300  10.000"
            "  1.00 20.00           C\n"
            "ATOM      3  C   ALA A   1      13.000   7.700  10.000"
            "  1.00 20.00           C\n"
            "ATOM      4  O   ALA A   1      12.400   8.700  10.000"
            "  1.00 20.00           O\n"
            "ATOM      5  N   ALA A   2      14.300   7.900  10.000"
            "  1.00 20.00           N\n"
            "ATOM      6  CA  ALA A   2      15.700   8.300  10.000"
            "  1.00 20.00           C\n"
            "ATOM      7  C   ALA A   2      16.100   9.700  10.000"
            "  1.00 20.00           C\n"
            "ATOM      8  O   ALA A   2      15.500  10.700  10.000"
            "  1.00 20.00           O\n"
            "HETATM    9 NA    NA A 101      30.000  30.000  30.000"
            "  1.00 20.00          NA\n"
            "END\n")
        (tmp_path / "dep").mkdir()
        (tmp_path / "dep" / "mini.pdb").write_text(pdb_text)
        segments, signatures = _run_segments(tmp_path / "dep",
                                             tmp_path / "run")
        ions = _ion_segments(segments, signatures)
        seg_sizes = {k: (v.get("properties") or {}).get(
            "atom_count_fragment") for k, v in segments.items()}
        assert any(v and str(v).strip().lower().startswith("na")
                   for v in ions.values()), (
            f"synthetic absorbed Na must split; segments: {seg_sizes}")
        # and the chain segment must NOT contain the Na
        chain = segments.get("A")
        if chain is not None:
            assert (chain.get("properties") or {}
                    ).get("atom_count_fragment") == 8, (
                "chain A must have shed the Na atom", chain)
