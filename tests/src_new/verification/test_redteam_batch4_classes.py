"""Red-team batch-4 (5.4) — D-06 equivalence classes keyed on reference content.

Old behavior: sequence-verified hits got 'align:{round(S/100,2)}' and
structure-verified hits 'tm:{round(S/100,2)}' — two records sharing ONLY a
rounded score collapsed into one 'same structure' class (probe d_p10:
UNIPROT P11111 and PDB 9XYZ both 'align:0.5'), and with the known fetcher
bug every structure hit was tm:0.0, so ALL structure hits of a segment
formed one class.

New rule: key on the REFERENCE CONTENT —
  seqref:<sha1-16(best matching reference sequence)> for sequence/structure
  verified hits (emitted additively by workers as
  VerificationScore.details['ref_seq_sha1']);
same reference at different identity scores => SAME class (the collapse now
means 'same underlying sequence/structure', which is what the UI presents).
Fallback when no reference content is known: record:<type>:<id> — never a
score-only class.
"""

from __future__ import annotations

import pytest

from src_new.verification.manager import _equivalence_class_id
from src_new.verification.models import VerificationScore, ref_seq_sha1
from src_new.verification.workers.sequence_worker import SequenceVerificationWorker
from src_new.verification.workers.structure_worker import StructureVerificationWorker


def _score(metric: str, value: float, details: dict | None = None) -> VerificationScore:
    return VerificationScore(kind="similarity", metric_name=metric,
                             raw_score=value / 100.0, normalized_score=value,
                             details=details or {})


class TestReferenceKeyedClasses:
    def test_score_bucket_no_longer_collapses_unrelated_records(self):
        """d_p10 reconstruction: P11111 vs 9XYZ sharing only S=50 differ."""
        donor_a = _score("seq_identity_coverage", 50.0,
                         {"ref_seq_sha1": ref_seq_sha1("AAAA")})
        donor_b = _score("seq_identity_coverage", 50.0,
                         {"ref_seq_sha1": ref_seq_sha1("GGGG")})
        cls_a = _equivalence_class_id("UNIPROT_ID", "P11111",
                                      "residue_sequence_protein", "AAAA", donor_a)
        cls_b = _equivalence_class_id("PDB_ID", "9XYZ",
                                      "residue_sequence_protein", "GGGG", donor_b)
        assert cls_a != cls_b
        assert cls_a.startswith("seqref:") and cls_b.startswith("seqref:")

    def test_same_reference_collapses_across_records_and_scores(self):
        """Two different records pointing at the SAME reference sequence are
        one class, even at different alignment scores (the UI collapse means
        'same underlying sequence')."""
        sha = ref_seq_sha1("MVLSPADK")
        cls_a = _equivalence_class_id("UNIPROT_ID", "P11111",
                                      "residue_sequence_protein", "MVLSPADK",
                                      _score("seq_identity_coverage", 97.0,
                                             {"ref_seq_sha1": sha}))
        cls_b = _equivalence_class_id("PDB_ID", "9XYZ",
                                      "residue_sequence_protein", "MVLSPADK",
                                      _score("seq_identity_coverage", 93.0,
                                             {"ref_seq_sha1": sha}))
        assert cls_a == cls_b == f"seqref:{sha}"

    def test_structure_hit_uses_reference_not_tm_bucket(self):
        sha = ref_seq_sha1("A" * 60)
        donor = _score("tm_score", 80.0, {"ref_seq_sha1": sha})
        cls = _equivalence_class_id("PDB_ID", "1ABC", "pdb_protein", "...", donor)
        assert cls == f"seqref:{sha}"
        assert not cls.startswith("tm:")

    def test_no_reference_content_falls_back_to_record(self):
        donor = _score("seq_identity_coverage", 50.0)  # no details
        cls = _equivalence_class_id("UNIPROT_ID", "P11111",
                                    "residue_sequence_protein", None, donor)
        assert cls == "record:UNIPROT_ID:P11111"
        cls_none = _equivalence_class_id("SWISSPROT_ID", "P99999",
                                         None, None, None)
        assert cls_none == "record:SWISSPROT_ID:P99999"

    def test_chemical_and_element_classes_unchanged(self):
        cls = _equivalence_class_id("PUBCHEM_CID", "702", None, "CCO", None)
        assert cls.startswith("skeleton:")
        assert _equivalence_class_id("ELEMENT", "NA", None, None, None) == "element:NA"


class TestWorkersEmitReferenceContent:
    def test_sequence_worker_details(self):
        worker = SequenceVerificationWorker()
        parent = "MKTIIALSYIFCLVFA" * 10
        domain = parent[20:80]
        score = worker.verify(domain, "X00000", "UNIPROT_ID", parent,
                              signature_type="residue_sequence_protein")
        assert score is not None
        assert score.details.get("ref_seq_sha1") == ref_seq_sha1(parent)

    def test_structure_tm_details(self):
        import math
        def helix(n, phase=0.0):
            return [[2.3 * math.cos(phase + i * 1.745),
                     2.3 * math.sin(phase + i * 1.745), 1.5 * i]
                    for i in range(n)]
        def pdb(n, phase):
            lines = ["HEADER X"]
            for i, (x, y, z) in enumerate(helix(n, phase), 1):
                lines.append(
                    f"ATOM  {i:5d} {'CA':^4s} {'ALA':>3s} A{i:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C")
            lines.append("TER\nEND\n")
            return "\n".join(lines)
        worker = StructureVerificationWorker()
        score = worker.verify(pdb(12, 0.0), "9XXX", "PDB_ID", pdb(60, 0.0),
                              signature_type="pdb_protein")
        assert score is not None
        assert score.details.get("ref_seq_sha1") == ref_seq_sha1("A" * 60)
