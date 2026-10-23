"""Red-team batch-4 (5.5) — D-02 fidelity ordering semantics.

D-02: the stored presentation order sorted by skeleton similarity and then
similarity_score, mapping a missing S to -1 — i.e. "unknown" sorted BELOW a
measured near-zero. Two live consequences: (a) chemical hits whose
representative signature was inchikey/formula/name got S=None and sank
below similarity-only rows even while two resolvers asserted identity on
them (d_p3: DPPC identity with belief 75 sorted below DMPC/DSPC
similarity-only rows); (b) rows verified by assertion (mmCIF identity)
sank below degenerate tm:0.0 rows (d_p4).

Fix pins:
  1. hits are verified against EVERY member signature of the group (the
     representative may be an inchikey while another member carries the
     smiles/fasta); the best applicable score wins.
  2. chemicals always get a multi-fingerprint comparison vs the molecule's
     own SMILES signature once a canonical SMILES was fetched — even when
     no member signature is worker-applicable.
  3. ordering tuple: skeleton bucket (0.05) desc -> is-identity desc ->
     similarity desc (None = -1) -> belief desc -> evidence count desc ->
     confidence desc -> identifier -> ident_type. hit_type is now persisted
     on VerifiedHit so the ordering knows it.
"""

from __future__ import annotations

import pytest

from src_new.verification.dedup import RawHit, deduplicate_and_score
from src_new.verification.manager import _fidelity_order_hits, _fidelity_order_key
from src_new.verification.models import VerificationScore


def _hit(identifier, *, hit_type=None, skeleton_sim=None, similarity_score=None,
         evidence=1, belief=None, confidence=50.0, verified=True, ident_type="PUBCHEM_CID"):
    from src_new.verification.models import VerifiedHit
    return VerifiedHit(
        identifier=identifier, ident_type=ident_type, database="pubchem",
        resolver_score=50.0, similarity_score=similarity_score,
        annotation_quality_score=None, final_confidence=confidence,
        supporting_evidence_count=evidence, is_verified=verified,
        skeleton_sim=skeleton_sim, belief=belief, hit_type=hit_type,
    )


class TestFidelityTuple:
    def test_dppc_identity_beats_dmpc_similarity(self):
        """d_p3 reconstruction: identity with S=None must not sink below
        similarity-only rows at the same skeleton bucket."""
        dppc = _hit("5498225", hit_type="identity", skeleton_sim=1.0,
                    similarity_score=None, evidence=2, belief=75.0,
                    confidence=70.0)
        dmpc = _hit("94160", hit_type="similarity", skeleton_sim=1.0,
                    similarity_score=96.49, evidence=1, belief=50.0,
                    confidence=46.85)
        ordered = _fidelity_order_hits([dmpc, dppc])
        assert [h.identifier for h in ordered] == ["5498225", "94160"]

    def test_mmcif_asserted_identity_beats_degenerate_tm(self):
        """d_p4 reconstruction: an asserted identity row beats a measured
        degenerate (0.0) similarity row even with S missing."""
        mmcif = _hit("3CCC", ident_type="PDB_ID", hit_type="identity",
                     skeleton_sim=None, similarity_score=None, evidence=1,
                     belief=50.0, confidence=20.0)
        tm0 = _hit("2BBB", ident_type="PDB_ID", hit_type="similarity",
                   skeleton_sim=None, similarity_score=0.0, evidence=1,
                   belief=50.0, confidence=8.3)
        ordered = _fidelity_order_hits([tm0, mmcif])
        assert [h.identifier for h in ordered] == ["3CCC", "2BBB"]

    def test_skeleton_bucket_is_coarse(self):
        """0.98 and 1.00 share one 0.05 bucket: the decisive key moves to
        identity/similarity, not to fp noise; 0.97 is one bucket below."""
        a = _hit("1", hit_type="similarity", skeleton_sim=0.98,
                 similarity_score=90.0)
        b = _hit("2", hit_type="similarity", skeleton_sim=1.0,
                 similarity_score=80.0)
        # same bucket -> similarity decides -> sim 90 row first
        assert _fidelity_order_key(a) < _fidelity_order_key(b)
        c = _hit("3", hit_type="similarity", skeleton_sim=0.97,
                 similarity_score=90.0)
        # 0.97 buckets below 0.98 -> second slot regardless of sim
        assert _fidelity_order_key(a) < _fidelity_order_key(c)

    def test_hit_type_persisted_on_verified_hit(self):
        hit = _hit("702", hit_type="identity")
        assert hit.hit_type == "identity"


class TestDedupMemberSignatures:
    def test_member_signatures_exposed(self):
        hits = [
            RawHit("702", "PUBCHEM_CID", "inchikey_self", 90.0,
                   "UYAHUIUNGNFGSP-UHFFFAOYSA-N", "inchikey", "identity"),
            RawHit("702", "PUBCHEM_CID", "formula_local", 60.0,
                   "CCO", "smiles", "similarity"),
        ]
        out = deduplicate_and_score(hits)
        meta = out[("702", "PUBCHEM_CID")]
        members = meta.get("member_signatures")
        assert members, "member_signatures missing from dedup metadata"
        types = [t for _s, t in members]
        assert "inchikey" in types and "smiles" in types
        # representative (highest resolver_score) comes first
        assert members[0][1] == "inchikey"


class _RecordingCompoundWorker:
    SUPPORTED_IDENT_TYPES = {"PUBCHEM_CID", "CHEMBL_ID", "CHEBI_ID"}

    def __init__(self, score=100.0):
        self.calls: list[tuple] = []
        self._score = score

    def is_applicable(self, signature_type, ident_type):
        return signature_type == "smiles" and ident_type in self.SUPPORTED_IDENT_TYPES

    def verify(self, signature, identifier, ident_type,
               canonical_signature=None, signature_type=None):
        self.calls.append((signature, identifier, ident_type,
                           canonical_signature, signature_type))
        return VerificationScore(
            kind="similarity", metric_name="multi_fingerprint_tanimoto",
            raw_score=self._score / 100.0, normalized_score=self._score,
            details={"smiles": signature},
        )


class _FakeFetcher:
    def __init__(self, canonical="CCO"):
        self._canonical = canonical

    def supports(self, ident_type):
        return True

    def fetch(self, identifier, ident_type):
        return self._canonical


def _manager(worker, fetcher=None):
    from types import SimpleNamespace
    from src_new.verification.manager import VerificationManager
    from src_new.config.loader import RunConfig

    mgr = VerificationManager.__new__(VerificationManager)
    mgr._registry = SimpleNamespace(
        get_fetcher=lambda ident_type, signature_type=None: fetcher,
        get_applicable_workers=lambda sig_type, ident_type: (
            [worker] if worker.is_applicable(sig_type, ident_type) else []),
        get_scorer=lambda *a, **k: None,
    )
    mgr._verification_config = RunConfig().verification
    return mgr


def _seed_chemical(results, segment, entries):
    for i, entry in enumerate(entries):
        results.set_data(f"identifiers/{segment}/genA/res{i}", entry)


class TestManagerGroupVerification:
    def test_every_member_signature_is_tried(self, tmp_path):
        """Group representative is an inchikey (workerless); the smiles
        member must still be verified (D-02 fix a)."""
        from src_new.results.results_manager import ResultsManager
        import time

        worker = _RecordingCompoundWorker(score=100.0)
        mgr = _manager(worker, _FakeFetcher("CCO"))
        results = ResultsManager(tmp_path / "results.json")
        _seed_chemical(results, "SEG1", [
            {"signature": "UYAHUIUNGNFGSP-UHFFFAOYSA-N",
             "hit_type": "identity", "hits": ["702"],
             "ident_type": "PUBCHEM_CID", "signature_type": "inchikey"},
            {"signature": "CCO",
             "hit_type": "similarity", "hits": [["702", 60.0]],
             "ident_type": "PUBCHEM_CID", "signature_type": "smiles"},
        ])
        mgr.verify_all(results, deadline_epoch=time.time() + 60)
        hits = results.get_data("verification/SEG1/verified_hits")
        assert hits, "no hits stored"
        stored = hits[0]
        # pre-fix: no worker ran against any member -> similarity_score None
        assert worker.calls, "compound worker never ran against any member"
        sigs = [c[0] for c in worker.calls]
        assert "CCO" in sigs, f"smiles member not verified: {sigs}"
        assert stored["similarity_score"] == 100.0, stored

    def test_chemical_multi_fp_vs_molecule_smiles(self, tmp_path):
        """No worker-applicable member signature at all; a fetched canonical
        SMILES must still be compared against the molecule's own generated
        smiles (D-02 fix b)."""
        from src_new.results.results_manager import ResultsManager
        import time

        worker = _RecordingCompoundWorker(score=100.0)
        mgr = _manager(worker, _FakeFetcher("CCO"))
        results = ResultsManager(tmp_path / "results.json")
        _seed_chemical(results, "SEG1", [
            {"signature": "UYAHUIUNGNFGSP-UHFFFAOYSA-N",
             "hit_type": "identity", "hits": ["702"],
             "ident_type": "PUBCHEM_CID", "signature_type": "inchikey"},
            {"signature": "ethanol",
             "hit_type": "similarity", "hits": [["702", 60.0]],
             "ident_type": "PUBCHEM_CID", "signature_type": "name_segment"},
        ])
        results.set_data("signatures/SEG1/generated/smiles", "CCO")
        mgr.verify_all(results, deadline_epoch=time.time() + 60)
        hits = results.get_data("verification/SEG1/verified_hits")
        assert hits, "no hits stored"
        stored = hits[0]
        assert worker.calls, "compound worker never ran"
        assert any(c[0] == "CCO" and c[4] == "smiles" for c in worker.calls), \
            f"molecule-smiles comparison not performed: {worker.calls}"
        assert stored["similarity_score"] == 100.0, stored

    def test_hit_type_threaded_to_stored_hit(self, tmp_path):
        from src_new.results.results_manager import ResultsManager
        import time

        worker = _RecordingCompoundWorker(score=100.0)
        mgr = _manager(worker, _FakeFetcher("CCO"))
        results = ResultsManager(tmp_path / "results.json")
        _seed_chemical(results, "SEG1", [
            {"signature": "UYAHUIUNGNFGSP-UHFFFAOYSA-N",
             "hit_type": "identity", "hits": ["702"],
             "ident_type": "PUBCHEM_CID", "signature_type": "inchikey"},
        ])
        results.set_data("signatures/SEG1/generated/smiles", "CCO")
        mgr.verify_all(results, deadline_epoch=time.time() + 60)
        stored = results.get_data("verification/SEG1/verified_hits")[0]
        assert stored.get("hit_type") == "identity", stored
