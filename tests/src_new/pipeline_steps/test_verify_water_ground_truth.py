"""Water ground-truth wiring tests (v3.140, run 99abca31 finding).

Regression guard: verify-stage workers run on a MINIMAL temp ResultsManager
(identifiers/signatures/universe-props only). fragments/segments was never
threaded, so _water_segment() evaluated False in the live pipeline and water
segments verified as generic chemicals (TIP3: 67 verified duplicates of one
identity instead of a single pinned water hit). These tests lock the wiring
gap itself (orchestrator builds the 6-tuple; worker threads the summary into
its temp manager); pin semantics lives in tests/src_new/verification/
test_water_ground_truth.py. Hermetic: VerificationManager.verify_all is
stubbed, no network.
"""

from __future__ import annotations

import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

import src_new.pipeline_steps.workers as workers_mod
from src_new.config.loader import RunConfig
from src_new.pipeline_steps import _verify_results
from src_new.pipeline_steps.workers import _verify_results_worker
from src_new.results.results_manager import ResultsManager

SEG = "seg_2_TIP3"
SEG_SUMMARY = [
    {"segment": "seg_0_TOCL2", "type": "lipid", "copies": 60, "atoms_per_copy": 248},
    {"segment": "seg_2_TIP3", "type": "water", "copies": 12000, "atoms_per_copy": 3},
]
IDENTIFIERS = {
    "sig": {"signature": "O", "hit_type": "identity", "hits": ["962"],
            "ident_type": "PUBCHEM_CID", "signature_type": "smiles"}
}


class _StubVerifyMgr:
    """Captures the temp manager the worker hands to verify_all."""

    def __init__(self, config):
        self.captured = {}

    def verify_all(self, results, deadline_epoch=None):
        self.captured["fragments"] = results.get_data("fragments/segments")
        self.captured["props"] = results.get_data(f"universe/segments/{SEG}/properties")
        results.set_data(f"verification/{SEG}/verified_hits", [])


def _cfg_dict():
    return RunConfig().to_dict()


# --- worker-level: 6-tuple threading -----------------------------------------

def test_worker_threads_segments_summary_into_temp_manager(monkeypatch):
    stub = _StubVerifyMgr(None)
    # worker imports VerificationManager lazily inside the function body
    # (from ..verification.manager import ...) — patch the source attribute.
    monkeypatch.setattr("src_new.verification.manager.VerificationManager", lambda cfg: stub)
    item = (SEG, IDENTIFIERS, _cfg_dict(), None, {"atom_count_fragment": 3}, SEG_SUMMARY)
    out = _verify_results_worker(item)
    assert stub.captured["fragments"] == SEG_SUMMARY
    assert stub.captured["props"] == {"atom_count_fragment": 3}
    assert out["segment"] == SEG and out["errors"] == []


def test_worker_tolerates_legacy_5_tuple(monkeypatch):
    stub = _StubVerifyMgr(None)
    monkeypatch.setattr("src_new.verification.manager.VerificationManager", lambda cfg: stub)
    item = (SEG, IDENTIFIERS, _cfg_dict(), None, {"atom_count_fragment": 3})
    out = _verify_results_worker(item)
    assert stub.captured["fragments"] is None      # pre-fix behavior = bug
    assert out["errors"] == []


# --- orchestrator-level: item construction ------------------------------------

def test_orchestrator_includes_segments_summary_in_items(monkeypatch, tmp_path):
    captured_items = []

    def fake_worker(item):
        captured_items.append(item)
        return {"segment": item[0], "verified_hits": [], "errors": []}

    monkeypatch.setattr("src_new.pipeline_steps.workers._verify_results_worker", fake_worker)

    results = ResultsManager(tmp_path / "results.json")
    results.set_data("identifiers", {SEG: IDENTIFIERS})
    results.set_data("fragments/segments", SEG_SUMMARY)

    class _FakeContext:
        def __init__(self):
            self.results = results
            self.config = RunConfig()
            self.warnings = []

        def get_value(self, key):
            return object() if key == "facade" else None

        def fail(self, code, msg):
            raise AssertionError(f"context.fail: {code}: {msg}")

    _verify_results(_FakeContext())
    assert len(captured_items) == 1
    item = captured_items[0]
    assert len(item) == 6
    assert item[5] == SEG_SUMMARY
