"""Red-team Batch 1.8 (misc resolver) regression tests.

  C-11: hfamily filled its total candidate cap from H-range..H upward, so
        the exact and protonated formulas ran out of budget first (probe:
        exact formula got 0/5000 candidates named after delta order).
  C-13: cache init OSError (unwritable/missing directory) escaped base
        .resolve() before the resolver ran — the whole identification
        stage silently zeroed on a bad cache path.
  C-16: stage deadline was only enforced BETWEEN resolvers; a single 300 s
        BLAST subprocess ran past it. Resolvers need budget-aware timeouts.
  C-18: the same UniProt accession arrived as SWISSPROT_ID (blast
        _swissprot) and UNIPROT_ID (blast_uniprot), so cross-channel
        consensus never formed.
"""
from __future__ import annotations

import time

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolver
from src_new.identification.cache_manager import ResolverCache
from src_new.identification.resolvers.blast import BLASTResolverSWISSPROT
from src_new.identification.resolvers.hfamily import FormulaHFamilyResolver


class _FakeLocalDb:
    """Every H-variant returns `per_query` distinct CIDs (name-encoded)."""

    def by_formula(self, formula: str, limit: int):
        return [f"{formula}#{i}" for i in range(limit)]


class TestC11HFamilyDeltaOrder:
    def _resolver(self) -> FormulaHFamilyResolver:
        r = FormulaHFamilyResolver(RunConfig())
        r._local_db = _FakeLocalDb()
        r._local_per_query = 40
        r._local_max_total = 100
        r.h_range = 2
        return r

    def test_exact_formula_is_queried_first(self, monkeypatch):
        r = self._resolver()
        queried = []
        orig = _FakeLocalDb.by_formula
        monkeypatch.setattr(r._local_db, "by_formula",
                            lambda f, limit: queried.append(f) or orig(r._local_db, f, limit))
        r._resolve_similarity("C20H25N3O", "")
        assert queried[0] == "C20H25N3O", (
            f"exact formula must be queried first, got order {queried}"
        )
        # |delta| order: 0, -1, +1, -2, +2
        assert queried == ["C20H25N3O", "C20H24N3O", "C20H26N3O",
                           "C20H23N3O", "C20H27N3O"]

    def test_exact_and_protonated_variants_survive_the_cap(self):
        """100 total / 5 variants: per-delta cap keeps EVERY variant — in
        simulations acids are deprotonated, so the neutral PubChem form
        (H+1/H+2) was exactly what the old fill order dropped."""
        r = self._resolver()
        cids = [cid for cid, _ in r._resolve_similarity("C20H25N3O", "")]
        assert len(cids) <= 100
        for variant in ("C20H25N3O", "C20H24N3O", "C20H26N3O",
                        "C20H23N3O", "C20H27N3O"):
            kept = [c for c in cids if c.startswith(variant + "#")]
            assert kept, f"{variant} starved by the candidate cap (C-11)"
        # per-delta share: no variant may exceed its share of the total cap
        for variant in ("C20H25N3O", "C20H24N3O", "C20H26N3O",
                        "C20H23N3O", "C20H27N3O"):
            kept = [c for c in cids if c.startswith(variant + "#")]
            assert len(kept) <= (100 // 5) + 1


class TestC13CacheOSError:
    def test_resolve_degrades_to_live_when_cache_read_oserrors(self):
        class _Toy(IdentifierResolver):
            name = "toy_c13"
            identifier_type = "X_ID"

            def _is_applicable(self, signature):
                return True

            def _resolve_identity(self, signature, working_directory):
                return ["HIT"]

            def _resolve_similarity(self, signature, working_directory):
                return [("HIT", 90.0)]

        class _OSErrorCache:
            def fetch_identity_identifiers(self, *_a, **_k):
                raise OSError(2, "No such file or directory: '/proc/nope'")

            def save_identity_identifiers(self, *_a, **_k):
                raise OSError(30, "Read-only file system")

        toy = _Toy(RunConfig())
        out = toy.resolve("sig", cache=_OSErrorCache())
        assert out == ["HIT"], (
            "cache OSError must degrade to a cache MISS, not zero the stage (C-13)"
        )

    def test_resolver_cache_disables_itself_after_init_failure(self):
        """Unwritable directory: first call logs once and goes no-op, later
        calls never retry the connect (was: exception on EVERY resolver)."""
        cfg = RunConfig()
        cfg.identifiers_cache.directory = "/proc/nonexistent_dir_for_probe_c13"
        cache = ResolverCache(cfg)
        assert cache.fetch_identity_identifiers("toy", "sig") == []
        assert cache._disabled is True
        # subsequent calls stay no-op without raising
        assert cache.fetch_identity_identifiers("toy", "sig") == []
        cache.save_identity_identifiers("toy", "sig", ["X"])
        assert cache.fetch_similarity_identifiers("toy", "sig") == []


class TestC16BudgetAwareTimeouts:
    def test_call_timeout_clamps_to_remaining_stage_budget(self):
        r = FormulaHFamilyResolver(RunConfig())
        r._stage_deadline_epoch = time.time() + 4
        assert r._call_timeout(300.0) <= 5.0
        r._stage_deadline_epoch = time.time() - 1
        assert 0.0 <= r._call_timeout(300.0) <= 1.0
        r._stage_deadline_epoch = None
        assert r._call_timeout(300.0) == 300.0


class TestC18UniProtCanonicalType:
    def test_blast_swissprot_emits_uniprot_id(self):
        r = BLASTResolverSWISSPROT(RunConfig())
        assert r.identifier_type == "UNIPROT_ID", (
            "SWISSPROT_ID must be folded into the canonical UNIPROT_ID so "
            "blast_swissprot + blast_uniprot + (sequence-mapped) hits merge "
            "into one consensus group (C-18); the source DB stays in the "
            "resolver name/metadata"
        )
        assert "swissprot" in r.name
