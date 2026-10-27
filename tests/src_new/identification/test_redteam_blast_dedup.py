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
