"""End-to-end tests: verify stage universe-property propagation.

Regression guard for the 2026-10-12 production finding (run 9d90d777): the
verify stage builds a MINIMAL per-segment temp ResultsManager and previously
transferred only identifiers + signatures. universe/segments/<seg>/properties
never reached the worker, so the element ground-truth rule (user ruling
2026-10-11) always saw atom_count=None and conservatively stayed at conf 80.

These tests run the REAL worker function and the REAL step orchestrator with
the default registry (element path is fully local: ElementVerificationWorker,
no fetcher/scorer for ELEMENT) — no network.
"""

from __future__ import annotations

import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

from src_new.config.loader import RunConfig
from src_new.pipeline_steps import _verify_results
from src_new.pipeline_steps.workers import _verify_results_worker
from src_new.results.results_manager import ResultsManager


SEG = "seg_6_SOD"

# Mirrors the real stored identifier state produced by the atom resolver
# (verified against live run 9d90d777 results.json).
ATOM_IDENTIFIERS = {
    "atom": {
        "atom": {
            "signature": "Na",
            "hit_type": "identity",
            "hits": ["Na"],
            "ident_type": "ELEMENT",
            "signature_type": "element",
        }
    }
}


def _cfg_dict():
    return RunConfig().to_dict()


def _run_worker(sig_data=None, props=None):
    return _verify_results_worker(
        (SEG, ATOM_IDENTIFIERS, _cfg_dict(), sig_data, props)
    )


def _hit(result, identifier="NA"):
    assert result["segment"] == SEG
    assert not result["errors"], f"worker errors: {result['errors']}"
    hits = [h for h in result["verified_hits"]
            if (h.get("identifier") if isinstance(h, dict) else getattr(h, "identifier")) == identifier]
    assert hits, f"no {identifier} hit in {result['verified_hits']}"
    h = hits[0]
    return h if isinstance(h, dict) else vars(h)


# --- worker-level end-to-end ------------------------------------------------

def test_worker_e2e_element_ground_truth_with_props():
    """Atom facts present -> monoatomic ELEMENT identity lifts to conf 100."""
    result = _run_worker(props={"atom_count_fragment": 1})
    h = _hit(result)
    assert h["is_verified"] is True
    assert h["final_confidence"] == 100.0
    assert h["ground_truth_override"] == "element_monoatomic"


def test_worker_e2e_without_props_stays_conservative():
    """Facts missing (pre-fix worker) -> weighted path, conf 80, no override."""
    result = _run_worker(props=None)
    h = _hit(result)
    assert h["is_verified"] is True
    assert h["final_confidence"] == 80.0
    assert h["ground_truth_override"] is None


def test_worker_e2e_polyatomic_guard():
    """Facts present but molecule multi-atom -> override must NOT fire."""
    result = _run_worker(props={"atom_count_fragment": 8})
    h = _hit(result)
    assert h["final_confidence"] == 80.0
    assert h["ground_truth_override"] is None


# --- orchestrator-level end-to-end ------------------------------------------

class _FakeContext:
    """Minimal pipeline context for the serial _verify_results path."""

    def __init__(self, results, config):
        self.results = results
        self.config = config
        self.warnings = []

    def get_value(self, key):
        if key == "facade":
            return object()  # truthy; presence check only
        return None          # no stage budget

    def fail(self, code, msg):
        raise AssertionError(f"context.fail: {code}: {msg}")

    def add_warning(self, code, msg):
        self.warnings.append((code, msg))


def _results_manager(tmp_path, with_props):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"pipeline_name": "t", "data": {}}))
    rm = ResultsManager(str(path), pipeline_name="t")
    for gen, gen_data in ATOM_IDENTIFIERS.items():
        rm.set_data(f"identifiers/{SEG}/{gen}", gen_data)
    if with_props is not None:
        rm.set_data(f"universe/segments/{SEG}/properties", with_props)
    return rm


def _stored_hit(ctx):
    hits = ctx.results.get_data(f"verification/{SEG}/verified_hits") or []
    assert hits, "verify step stored no hits"
    h = hits[0]
    return h if isinstance(h, dict) else vars(h)


def test_verify_results_step_wires_universe_properties(tmp_path):
    """Full step: context.payload -> worker items -> stored verification has
    the ground-truth override (the production regression path)."""
    ctx = _FakeContext(_results_manager(tmp_path, {"atom_count_fragment": 1}), RunConfig())
    out = _verify_results(ctx)
    h = _stored_hit(ctx)
    assert h["final_confidence"] == 100.0
    assert h["ground_truth_override"] == "element_monoatomic"
    assert not ctx.warnings


def test_verify_results_step_without_props_stays_conservative(tmp_path):
    """Full step with an older payload lacking universe facts -> 80, no flag."""
    ctx = _FakeContext(_results_manager(tmp_path, None), RunConfig())
    out = _verify_results(ctx)
    h = _stored_hit(ctx)
    assert h["final_confidence"] == 80.0
    assert h["ground_truth_override"] is None
