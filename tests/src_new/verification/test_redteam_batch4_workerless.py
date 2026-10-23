"""Red-team batch-4 (5.7) — D-09 workerless types get real comparisons.

D-09: Foldseek UniProt hits, mmCIF/topology-less PDB hits, and LipidMaps /
GlyTouCan hits were verified by RECORD EXISTENCE alone (fetch succeeds /
annotation > 0) rather than any molecule-vs-record comparison.

Fix pins:
  - UNIPROT_ID / SWISSPROT_ID arriving on STRUCTURE signatures (Foldseek's
    ca_only_pdb etc.) run through the sequence worker: the CA-trace
    sequence is extracted and locally aligned against the fetched UniProt
    FASTA. The structure worker keeps PDB/AF-family types (its fetchers can
    serve them); the sequence worker does not hijack those pairings.
  - `annotation_score > 0` alone is no longer positive evidence —
    existence of an annotated record is not corroboration.
  - LM_ID / GLYTOUCAN_ID join the chemical gate: identity alone cannot
    verify a lipid/glycan row; corroboration requires the fetched
    structure. LMSD's REST smiles endpoint (live shape recorded 2026-10-23)
    supplies LM_ID canonical SMILES. GLYTOUCAN_ID gets no fetcher yet —
    unverifiable rather than verified-by-existence (documented).
  - NR/NT stay unchanged this batch (no scorer exists for them, so the
    annotation-removal cannot affect them; C-10 tri-state lands in TASK 6).
"""

from __future__ import annotations

import math

import pytest

from src_new.verification.fetchers.compound_fetcher import CompoundSignatureFetcher
from src_new.verification.fetchers.sequence_fetcher import SequenceSignatureFetcher
from src_new.verification.models import CHEMICAL_IDENT_TYPES
from src_new.verification.registry import get_default_registry
from src_new.verification.workers.sequence_worker import SequenceVerificationWorker
from src_new.verification.workers.structure_worker import StructureVerificationWorker


def _ca_only_pdb(chain: str, seq_three: list[str]) -> str:
    """Minimal CA-only structure string with the given residue sequence."""
    lines = ["HEADER    SYNTH CA-ONLY"]
    for i, resname in enumerate(seq_three, 1):
        t = i * 1.745
        x, y, z = 2.3 * math.cos(t), 2.3 * math.sin(t), 1.5 * i
        lines.append(
            f"ATOM  {i:5d} {'CA':^4s} {resname:>3s} {chain}{i:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C")
    lines += ["TER", "END"]
    return "\n".join(lines) + "\n"


_ALA8 = ["ALA"] * 8  # seq "AAAAAAAA"


class TestSequenceFromStructureSignatures:
    def test_uniprot_on_structure_signature_applicable(self):
        w = SequenceVerificationWorker()
        assert w.is_applicable("ca_only_pdb", "UNIPROT_ID") is True
        assert w.is_applicable("mmcif", "UNIPROT_ID") is True
        assert w.is_applicable("pdb_protein", "SWISSPROT_ID") is True

    def test_structure_worker_types_not_hijacked(self):
        """PDB/AF-family types keep going to the structure worker (its
        fetchers serve them) — the sequence worker must not shadow them."""
        w = SequenceVerificationWorker()
        assert StructureVerificationWorker().is_applicable(
            "ca_only_pdb", "PDB_ID") is True
        assert w.is_applicable("ca_only_pdb", "PDB_ID") is False
        assert w.is_applicable("ca_only_pdb", "ALPHAFOLD_ID") is False

    def test_fasta_signatures_still_accepted(self):
        w = SequenceVerificationWorker()
        assert w.is_applicable("residue_sequence_protein", "UNIPROT_ID") is True

    def test_verify_extracts_trace_sequence_and_compares(self):
        """A Foldseek UniProt hit: CA-trace residues embedded in a longer
        UniProt FASTA must score high (local alignment, 5.2 semantics)."""
        worker = SequenceVerificationWorker()
        signature = _ca_only_pdb("A", _ALA8)
        canonical = "MKVL" + "A" * 8 + "GGGGG"  # trace is a perfect fragment
        score = worker.verify(signature, "P00698", "UNIPROT_ID", canonical,
                              signature_type="ca_only_pdb")
        assert score is not None
        assert score.metric_name == "seq_identity_coverage"
        assert score.normalized_score >= 90.0, score
        assert score.details.get("query_coverage") is not None

    def test_unparsable_structure_signature_returns_none(self):
        worker = SequenceVerificationWorker()
        assert worker.verify("NOT A STRUCTURE", "P00698", "UNIPROT_ID",
                             "AAAAAAA", signature_type="ca_only_pdb") is None

    def test_fetcher_routing_uniprot_structure_sig(self):
        """Routing consistency: structure signatures for UNIPROT must still
        fetch the UniProt FASTA (structure fetcher can't serve UniProt)."""
        registry = get_default_registry()
        fetcher = registry.get_fetcher("UNIPROT_ID", signature_type="ca_only_pdb")
        assert isinstance(fetcher, SequenceSignatureFetcher)


class TestAnnotationAloneNotEvidence:
    def _mgr_stub(self):
        from types import SimpleNamespace
        from src_new.verification.manager import VerificationManager
        from src_new.verification.models import AnnotationQuality
        from src_new.config.loader import RunConfig

        mgr = VerificationManager.__new__(VerificationManager)
        mgr._registry = SimpleNamespace(
            get_fetcher=lambda ident_type, signature_type=None: None,
            get_applicable_workers=lambda *a, **k: [],
            get_scorer=lambda *a, **k: SimpleNamespace(
                score=lambda ident, it: AnnotationQuality(
                    database="stub", score=100.0, signals=["exists"])),
        )
        mgr._verification_config = RunConfig().verification
        return mgr

    def test_similarity_hit_with_annotation_only_not_verified(self, tmp_path):
        """d_p9 core pin: annotation_score 100 (record exists) but no
        comparison performed -> NOT verified (pre-fix: verified)."""
        import time
        from src_new.results.results_manager import ResultsManager

        mgr = self._mgr_stub()
        results = ResultsManager(tmp_path / "results.json")
        results.set_data("identifiers/SEG1/genA/res0", {
            "signature": "MKVL", "hit_type": "similarity",
            "hits": [["P99999", 80.0]], "ident_type": "UNIPROT_ID",
            "signature_type": "residue_sequence_protein"})
        mgr.verify_all(results, deadline_epoch=time.time() + 60)
        stored = results.get_data("verification/SEG1/verified_hits")[0]
        assert stored["is_verified"] is False, stored

    def test_identity_hit_still_verified(self, tmp_path):
        """Identity (resolver-asserted exact record) still verifies — the
        annotation term was never what carried it."""
        import time
        from src_new.results.results_manager import ResultsManager

        mgr = self._mgr_stub()
        results = ResultsManager(tmp_path / "results.json")
        results.set_data("identifiers/SEG1/genA/res0", {
            "signature": "MKVL", "hit_type": "identity",
            "hits": ["P00698"], "ident_type": "UNIPROT_ID",
            "signature_type": "residue_sequence_protein"})
        mgr.verify_all(results, deadline_epoch=time.time() + 60)
        stored = results.get_data("verification/SEG1/verified_hits")[0]
        assert stored["is_verified"] is True


class TestLipidChemicalGate:
    def test_lm_and_glytoucan_in_chemical_gate(self):
        assert "LM_ID" in CHEMICAL_IDENT_TYPES
        assert "GLYTOUCAN_ID" in CHEMICAL_IDENT_TYPES

    def test_compound_fetcher_supports_lm(self):
        assert CompoundSignatureFetcher().supports("LM_ID") is True


class TestLmsdFetch:
    def test_lmsd_smiles_shape(self):
        """Recorded live 2026-10-23: /rest/compound/lm_id/{id}/smiles ->
        {"input": ..., "smiles": ...}."""
        import json
        from pathlib import Path
        from unittest.mock import Mock, patch

        fixture = Path(__file__).parent / "fixtures" / "d09" / \
            "lmsd_LMGP01010569_smiles.json"
        payload = json.loads(fixture.read_text())
        with patch("src_new.verification.fetchers.compound_fetcher.requests.get") as g:
            g.return_value = Mock(status_code=200, json=lambda: payload,
                                  raise_for_status=lambda: None)
            out = CompoundSignatureFetcher().fetch("LMGP01010569", "LM_ID")
        assert out == payload["smiles"]
        assert out.startswith("[C@](")  # stereo SMILES recorded live


class TestLipidExistenceNotEnough:
    def test_lm_identity_without_structure_not_verified(self, tmp_path):
        """An LM_ID identity row with no fetchable structure can no longer
        verify on existence alone (chemical gate)."""
        import time
        from types import SimpleNamespace
        from src_new.results.results_manager import ResultsManager
        from src_new.verification.manager import VerificationManager
        from src_new.config.loader import RunConfig

        mgr = VerificationManager.__new__(VerificationManager)
        mgr._registry = SimpleNamespace(
            get_fetcher=lambda ident_type, signature_type=None: None,
            get_applicable_workers=lambda *a, **k: [],
            get_scorer=lambda *a, **k: None,
        )
        mgr._verification_config = RunConfig().verification

        results = ResultsManager(tmp_path / "results.json")
        results.set_data("identifiers/SEG1/genA/res0", {
            "signature": "DMPC", "hit_type": "identity",
            "hits": ["LMGP01010569"], "ident_type": "LM_ID",
            "signature_type": "resname"})
        mgr.verify_all(results, deadline_epoch=time.time() + 60)
        stored = results.get_data("verification/SEG1/verified_hits")[0]
        assert stored["is_verified"] is False, stored


class TestNcbiScopeUnchanged:
    def test_ncbi_types_not_chemical(self):
        assert "NR_ID" not in CHEMICAL_IDENT_TYPES
        assert "NT_ID" not in CHEMICAL_IDENT_TYPES
