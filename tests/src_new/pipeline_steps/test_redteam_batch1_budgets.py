"""Red-team Batch 1.2 (budgets chain) regression tests.

  E-01: set_stage_budget calls context.set_value(), which does not exist on
        StepContext -> stage budgets have never armed in the pipeline path.
  D-04: verify_all drops the current segment's already-gathered hits when the
        budget expires mid-segment (returns before writing verified_hits);
        the parallel path never sets budget_hit.
  D-14: one malformed hit aborts the whole segment and the empty result is
        filed under segment "unknown".
"""
from __future__ import annotations

import logging
import time
from types import SimpleNamespace

import pytest

from src_new.config.loader import RunConfig
from src_new.executor.task import StepContext, TaskContext
from src_new.pipeline_steps import (
    _budget_exceeded,
    _STAGE_BUDGET_STATE_KEY,
    budget_deadline,
    set_stage_budget,
)
from src_new.results.results_manager import ResultsManager


def _real_context(tmp_path) -> TaskContext:
    results = ResultsManager.__new__(ResultsManager)
    return TaskContext(
        results=results,
        state={},
        working_directory=tmp_path,
        output_directory=tmp_path,
        logger=logging.getLogger("test"),
        config=RunConfig(),
    )


class TestE01SetValue:
    def test_step_context_has_set_value(self, tmp_path):
        """E-01: the budget mechanism writes through set_value; it must exist
        on the REAL context, not only on MagicMock."""
        ctx = _real_context(tmp_path)
        assert hasattr(ctx, "set_value"), (
            "StepContext lacks set_value — stage budgets can never arm (E-01)"
        )
        ctx.set_value("k", 42)
        assert ctx.get_value("k") == 42

    def test_set_stage_budget_arms_real_context(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VALIDATION_STAGE_BUDGETS", '{"verify_results": 30}')
        ctx = _real_context(tmp_path)
        set_stage_budget(ctx, "verify_results")
        dl = budget_deadline(ctx)
        assert dl is not None, "deadline was never stored (set_value missing)"
        assert _budget_exceeded(ctx) is False
        ctx.set_value(_STAGE_BUDGET_STATE_KEY, time.time() - 1)
        assert _budget_exceeded(ctx) is True


def _verify_manager_stub():
    """VerificationManager with a stubbed registry (no network, no fetchers)."""
    from src_new.verification.manager import VerificationManager

    mgr = VerificationManager.__new__(VerificationManager)
    mgr._registry = SimpleNamespace(
        get_fetcher=lambda ident_type: None,
        get_applicable_workers=lambda *a, **k: [],
        get_scorer=lambda *a, **k: None,
    )
    mgr._verification_config = RunConfig().verification
    return mgr


def _seed_segment(results: ResultsManager, segment: str, ids: list[str]):
    for i, ident in enumerate(ids):
        results.set_data(
            f"identifiers/{segment}/genA/res{i}",
            {
                "signature": "MKVL",
                "hit_type": "identity",
                "hits": [ident],
                "ident_type": "UNIPROT_ID",
                "signature_type": "fasta",
            },
        )


class TestD04PartialKeep:
    def test_budget_cut_keeps_partial_hits_and_flags(self, tmp_path, monkeypatch):
        """Two candidates; the clock flips past the deadline while candidate 1
        is processed. Post-fix: the gathered hit is STORED and the segment is
        flagged partial (pre-fix: nothing stored at all)."""
        mgr = _verify_manager_stub()
        results = ResultsManager(tmp_path / "results.json")
        _seed_segment(results, "SEG1", ["P00001", "P00002"])

        now = time.time()
        state = {"past": False}
        real_time = time.time

        def fake_time():
            return now + 9999 if state["past"] else real_time()

        monkeypatch.setattr(time, "time", fake_time)

        # Flip the clock as candidate 1 is being processed: get_fetcher is
        # consulted exactly once per candidate inside the loop.
        fetch_calls = {"n": 0}

        def _get_fetcher(ident_type, signature_type=None):
            fetch_calls["n"] += 1
            if fetch_calls["n"] >= 1:
                # Flip DURING candidate 1's processing; the loop-top budget
                # check before candidate 2 then trips with 1 hit gathered.
                state["past"] = True
            return None

        mgr._registry = SimpleNamespace(
            get_fetcher=_get_fetcher,
            get_applicable_workers=lambda *a, **k: [],
            get_scorer=lambda *a, **k: None,
        )

        out = mgr.verify_all(results, deadline_epoch=now + 5)

        stored = results.get_data("verification/SEG1/verified_hits")
        assert stored is not None, (
            "budget cut mid-segment discarded the gathered hits (D-04)"
        )
        assert len(stored) == 1, (
            f"partial keep: expected the 1 gathered hit, got {stored!r}"
        )
        assert results.get_data("verification/SEG1/partial") is True
        assert len(out.get("SEG1", [])) == 1

    def test_past_deadline_first_candidate_still_stores_segment(self, tmp_path):
        mgr = _verify_manager_stub()
        results = ResultsManager(tmp_path / "results.json")
        _seed_segment(results, "SEG1", ["P00001", "P00002"])
        mgr.verify_all(results, deadline_epoch=time.time() - 1)
        # Pre-budget-expiry: the pre-segment check returns before the segment
        # starts — but a segment-level entry must still exist (empty + partial)
        # rather than being silently absent.
        assert results.get_data("verification/SEG1/partial") is True
        assert results.get_data("verification/SEG1/verified_hits") == []


class TestD14MalformedHits:
    def test_collect_hits_skips_malformed_scores(self, tmp_path):
        from src_new.verification.dedup import collect_hits

        results = ResultsManager(tmp_path / "results.json")
        results.set_data(
            "identifiers/SEG/genA/resA",
            {
                "signature": "s",
                "hit_type": "similarity",
                "hits": [["GOOD", 0.9], ["BAD", None], ["ALSO_BAD", "n/a"]],
                "ident_type": "UNIPROT_ID",
                "signature_type": "fasta",
            },
        )
        hits = collect_hits(results, "SEG")
        assert [h.identifier for h in hits] == ["GOOD"], (
            "malformed scores must be skipped, not abort the segment (D-14)"
        )

    def test_worker_attributes_failure_to_real_segment(self, monkeypatch, tmp_path):
        import src_new.pipeline_steps.workers as workers
        import src_new.verification.manager as mgr_mod

        def _boom(*a, **k):
            raise RuntimeError("resolver regression")

        monkeypatch.setattr(mgr_mod, "VerificationManager", _boom)
        item = ("seg_REAL", {}, RunConfig().to_dict(), None, None, None)
        out = workers._verify_results_worker(item)
        assert out["segment"] == "seg_REAL", (
            "failures filed under segment 'unknown' lose attribution and "
            "overwrite each other (D-14)"
        )
        assert out["verified_hits"] == []
