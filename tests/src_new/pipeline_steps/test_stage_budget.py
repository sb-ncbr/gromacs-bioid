"""Tests for the cooperative stage time budget mechanism (2026-09-19 stall fix)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


class TestBudgetHelpers:
    def test_stage_budget_seconds_default(self, monkeypatch):
        monkeypatch.delenv("VALIDATION_STAGE_BUDGETS", raising=False)
        from src_new.pipeline_steps import _stage_budget_seconds
        assert _stage_budget_seconds("generate_signatures") == 1200
        assert _stage_budget_seconds("some_other_stage") >= 900

    def test_stage_budget_seconds_json_override(self, monkeypatch):
        monkeypatch.setenv("VALIDATION_STAGE_BUDGETS", '{"verify_results": 42}')
        from src_new.pipeline_steps import _stage_budget_seconds
        assert _stage_budget_seconds("verify_results") == 42
        # defaults preserved for other stages
        assert _stage_budget_seconds("identify_molecules") == 1200

    def test_stage_budget_disabled_by_env(self, monkeypatch):
        monkeypatch.setenv("VALIDATION_STAGE_BUDGETS", "off")
        from src_new.pipeline_steps import _stage_budget_seconds
        assert _stage_budget_seconds("verify_results") is None

    def test_budget_exceeded(self):
        from src_new.pipeline_steps import _budget_exceeded, set_stage_budget
        ctx = MagicMock()
        ctx.get_value.return_value = time.time() - 1  # past
        assert _budget_exceeded(ctx) is True
        ctx.get_value.return_value = time.time() + 1000  # future
        assert _budget_exceeded(ctx) is False
        ctx.get_value.return_value = None
        assert _budget_exceeded(ctx) is False


class TestManagerDeadline:
    def _mgr_and_results(self):
        from src_new.verification.manager import VerificationManager
        from src_new.verification.registry import VerificationRegistry

        cfg = MagicMock()
        cfg.verification = MagicMock(
            verify_top_n=5, resolver_weight=0.4, similarity_weight=0.4,
            annotation_weight=0.2, min_final_confidence=0.0,
        )
        reg = VerificationRegistry(workers=[], fetchers=[], scorers=[])
        mgr = VerificationManager(cfg, registry=reg)
        results = MagicMock()
        results.get_data.side_effect = lambda p, *a, **k: (
            {"A": {"smiles": {"res": {"ident_type": "CHEMBL_ID", "hits": [], "signature": "CC"}}}}
            if p == "identifiers" else None
        )
        results.data_exists.return_value = True
        return mgr, results

    def test_past_deadline_returns_empty_immediately(self):
        mgr, results = self._mgr_and_results()
        out = mgr.verify_all(results, deadline_epoch=time.time() - 1)
        assert out == {}

    def test_no_deadline_unchanged(self):
        mgr, results = self._mgr_and_results()
        out = mgr.verify_all(results)  # legacy path: collect/dedup may still process
        assert isinstance(out, dict)
