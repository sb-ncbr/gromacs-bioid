"""Wave-2 item 9 (GitHub #1): BLAST failure caching + duplicate-signature
dedup.

9a) BLASTResolver._processed_hits caches FAILURES per (db_path, sequence)
    and re-raises them — a deterministic blastp timeout was paid once by
    the identity tier and AGAIN by the similarity tier.
9b) _identify_molecules_worker resolves each (signature_type, signature)
    pair once per segment — fasta variant generators can emit byte-equal
    signatures for the same segment.
"""

from unittest import mock

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolution_manager import IdentifierResolutionManager
from src_new.identification.resolvers.blast import BLASTResolver
from src_new.pipeline_steps.workers import _identify_molecules_worker


class TestBlastFailureCaching:
    def _resolver(self):
        r = object.__new__(BLASTResolver)
        r.db_path = "/fake/db"
        return r

    def test_timeout_cached_and_reraised_once(self):
        r = self._resolver()
        with mock.patch.object(
            r, "_run_blast_local", side_effect=RuntimeError("blast timeout")
        ) as spy:
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    r._processed_hits("ACDEFGHIK", "/tmp")
            assert spy.call_count == 1  # one timeout per (resolver, sequence) per run

    def test_success_still_cached(self):
        r = self._resolver()
        with mock.patch.object(r, "_run_blast_local", return_value="<xml/>") as spy_run, \
             mock.patch.object(r, "_process_blast_results",
                               return_value=["hit"]):
            assert r._processed_hits("ACDEFGHIK", "/tmp") == ["hit"]
            assert r._processed_hits("ACDEFGHIK", "/tmp") == ["hit"]
            assert spy_run.call_count == 1

    def test_different_sequences_not_conflated(self):
        r = self._resolver()
        with mock.patch.object(
            r, "_run_blast_local", side_effect=RuntimeError("blast timeout")
        ) as spy:
            for seq in ("ACDEFGHIK", "MKTIIALSY"):
                with pytest.raises(RuntimeError):
                    r._processed_hits(seq, "/tmp")
            assert spy.call_count == 2


class TestWorkerSignatureDedup:
    def test_identical_type_signature_resolved_once_per_segment(self):
        calls = []

        def counting_resolve(self, **kwargs):
            calls.append(kwargs["signature_generator_name"])

        item = (
            "segA",
            {"genA": "ACDEFGHIK", "genB": "ACDEFGHIK", "genC": "MKTIIAL"},
            RunConfig().to_dict(),
            {"genA": "residue_sequence_protein",
             "genB": "residue_sequence_protein",
             "genC": "residue_sequence_protein"},
            {},
        )
        with mock.patch.object(IdentifierResolutionManager, "resolve",
                               counting_resolve):
            result = _identify_molecules_worker(item)
        assert result["fragment_name"] == "segA"
        # genB carries the SAME (type, signature) as genA -> skipped
        assert calls == ["genA", "genC"]

    def test_same_signature_different_type_both_resolved(self):
        calls = []

        def counting_resolve(self, **kwargs):
            calls.append(kwargs["signature_generator_name"])

        item = (
            "segA",
            {"genA": "ACDEFGHIK", "genB": "ACDEFGHIK"},
            RunConfig().to_dict(),
            {"genA": "residue_sequence_protein",
             "genB": "residue_sequence_nucleotide"},
            {},
        )
        with mock.patch.object(IdentifierResolutionManager, "resolve",
                               counting_resolve):
            _identify_molecules_worker(item)
        assert calls == ["genA", "genB"]


class TestShortNucleotideRelaxedIdentity:
    """wave-2 item 10b: short NA (<= _SHORT_IDENTITY_MAX_QLEN) identity
    acceptance at >= 0.9 identity / >= 0.9 query coverage. The F-N1c
    absolute-exact claim (1.0/1.0/subject_len==query_len) stays the only
    'exact' path; relaxed hits carry their own metadata note."""

    def _nt_resolver(self, hits):
        r = object.__new__(BLASTResolver)
        r.is_protein = False
        r.blast_config = RunConfig().blast
        return r

    def _hit(self, identity, cov, subject_len, acc="nt.1"):
        from src_new.identification.resolvers.blast import BlastHit
        return BlastHit(accessions=[acc], evalue=50.0, bits=5.0,
                        identity_p=identity, coverage_p=cov,
                        subject_len=subject_len)

    def test_relaxed_hit_accepted_with_own_note(self):
        # 20-mer at 95% identity over full query against its OWN-LENGTH
        # subject (both directions hold)
        hits = [self._hit(0.95, 1.0, subject_len=20)]
        r = self._nt_resolver(hits)
        with mock.patch.object(r, "_processed_hits", return_value=hits):
            accepted = r._run_blast_identity("ACGTACGTACGTACGTACGT", "/tmp")
        assert accepted == ["nt.1"]
        assert r._last_resolution_metadata["nt.1"]["note"] == \
            "short_na_identity_ge_0.9_len_le_25"

    def test_relaxed_hit_inside_longer_subject_refused(self):
        # F-N1c both-directionality: 95% match INSIDE a longer subject is
        # NOT the same molecule, relaxed floor or not
        hits = [self._hit(0.95, 1.0, subject_len=400, acc="contained")]
        r = self._nt_resolver(hits)
        with mock.patch.object(r, "_processed_hits", return_value=hits):
            accepted = r._run_blast_identity("ACGTACGTACGTACGTACGT", "/tmp")
        assert accepted == []

    def test_below_relaxed_floor_not_accepted(self):
        hits = [self._hit(0.85, 1.0, subject_len=400, acc="weak")]
        r = self._nt_resolver(hits)
        with mock.patch.object(r, "_processed_hits", return_value=hits):
            accepted = r._run_blast_identity("ACGTACGTACGTACGTACGT", "/tmp")
        assert accepted == []

    def test_exact_fn1c_claim_unchanged(self):
        # perfect self-length match keeps the F-N1c 'exact' note
        hits = [self._hit(1.0, 1.0, subject_len=20, acc="exact1")]
        r = self._nt_resolver(hits)
        with mock.patch.object(r, "_processed_hits", return_value=hits):
            accepted = r._run_blast_identity("ACGTACGTACGTACGTACGT", "/tmp")
        assert accepted == ["exact1"]
        assert r._last_resolution_metadata["exact1"]["note"] == \
            "exact_short_identity_len_le_25"

    def test_long_sequences_not_relaxed(self):
        # > 25 nt: the relaxed short-NA path must NOT apply
        hits = [self._hit(0.95, 1.0, subject_len=600, acc="long")]
        r = self._nt_resolver(hits)
        seq = "A" * 60
        with mock.patch.object(r, "_processed_hits", return_value=hits):
            accepted = r._run_blast_identity(seq, "/tmp")
        assert accepted == []
