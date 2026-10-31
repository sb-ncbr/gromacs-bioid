"""W3.2 A7: verify_results runs once per resolution GROUP, not per segment.

Production evidence (W3 package, b954adc33 online logs): identify groups
P23 into 4 resolution groups (GroEL/GroES/Mg/ADP), but verify_results
still ran once per segment (35 calls); the InChIKey
XUVWGNKSYIFPIN-UHFFFAOYSA-N was fetched 3 times (~5 min each on the
firewalled workstation) and the 1200 s budget cut verification at D_1
(67/100 hits), leaving 7/35 segments answered and GroES O-U with none.

Fix contract pinned here (W3.2 item 1):
1. Segments carrying ``identifiers/<seg>/_shared_with`` are GROUP
   MEMBERS: the verify worker is invoked only for representatives and
   ungrouped segments (worker call count == number of groups).
2. A member's verification output is copied from its representative
   (identical content => identical verification), with its own
   ``verification/<member>/_shared_with`` marker.
3. Budget cuts drop WHOLE groups: a member never has verification
   output unless its representative does.
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

from src_new.config.loader import RunConfig
from src_new.pipeline_steps import _verify_results
from src_new.results.results_manager import ResultsManager


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


def _cfg():
    cfg = RunConfig()
    cfg.executor.verification_parallel = False  # exercise the serial loop
    return cfg


def _identifiers() -> dict:
    """6 segments, 2 groups + 1 unique (P23-like shape, shrunk).

    A_1 rep with member B_1; O rep with members P_1, Q_1; C_1 unique.
    """
    return {
        "A_1": {"atom": {"hits": ["X"], "ident_type": "ELEMENT"}},
        "B_1": {"atom": {"hits": ["X"], "ident_type": "ELEMENT"},
                "_shared_with": "A_1"},
        "C_1": {"atom": {"hits": ["Y"], "ident_type": "ELEMENT"}},
        "O":   {"atom": {"hits": ["Z"], "ident_type": "ELEMENT"}},
        "P_1": {"atom": {"hits": ["Z"], "ident_type": "ELEMENT"},
                "_shared_with": "O"},
        "Q_1": {"atom": {"hits": ["Z"], "ident_type": "ELEMENT"},
                "_shared_with": "O"},
    }


def _results(tmp_path, identifiers) -> ResultsManager:
    path = tmp_path / "results.json"
    path.write_text('{"pipeline_name": "t", "data": {}}')
    rm = ResultsManager(str(path), pipeline_name="t")
    for seg, blob in identifiers.items():
        rm.set_data(f"identifiers/{seg}", blob)
    return rm


@pytest.fixture()
def worker_calls(monkeypatch):
    calls: list[str] = []

    def stub_worker(item):
        seg = item[0]
        calls.append(seg)
        return {"segment": seg,
                "verified_hits": [{"identifier": f"hit-{seg}",
                                   "is_verified": True,
                                   "equivalence_class_id": "c1"}],
                "errors": [], "partial": False}

    import src_new.pipeline_steps.workers as workers_mod
    monkeypatch.setattr(workers_mod, "_verify_results_worker", stub_worker)
    return calls


def test_verify_runs_once_per_group(tmp_path, worker_calls):
    rm = _results(tmp_path, _identifiers())
    ctx = _FakeContext(rm, _cfg())
    _verify_results(ctx)
    # 6 segments, 3 verification targets (A_1, C_1, O) — members never run
    assert sorted(worker_calls) == ["A_1", "C_1", "O"], (
        f"worker invoked per segment, not per group: {worker_calls}")


def test_members_get_identical_output_and_marker(tmp_path, worker_calls):
    rm = _results(tmp_path, _identifiers())
    ctx = _FakeContext(rm, _cfg())
    _verify_results(ctx)
    for member, rep in (("B_1", "A_1"), ("P_1", "O"), ("Q_1", "O")):
        got = rm.get_data(f"verification/{member}/verified_hits")
        rep_hits = rm.get_data(f"verification/{rep}/verified_hits")
        assert got == rep_hits, f"{member} verification != representative {rep}"
        assert rm.get_data(f"verification/{member}/_shared_with") == rep
        assert rm.get_data(f"verification/{member}/class_sizes") == \
            rm.get_data(f"verification/{rep}/class_sizes")


def test_budget_cut_leaves_whole_groups(tmp_path, worker_calls, monkeypatch):
    """Deadline after the first group: A_1 verified (B_1 copied — the
    group completed atomically), everything else has NO verification."""
    import src_new.pipeline_steps as steps_mod
    state = {"n": 0}

    def fake_exceeded(context):
        state["n"] += 1
        return state["n"] > 1  # first budget check passes, second cuts

    monkeypatch.setattr(steps_mod, "_budget_exceeded", fake_exceeded)
    rm = _results(tmp_path, _identifiers())
    ctx = _FakeContext(rm, _cfg())
    out = _verify_results(ctx)
    assert sorted(worker_calls) == ["A_1"], worker_calls
    # the one completed group is fully materialized, members included
    assert rm.get_data("verification/A_1/verified_hits") is not None
    assert rm.get_data("verification/B_1/verified_hits") == \
        rm.get_data("verification/A_1/verified_hits")
    # every other group (and its members) is entirely unverified
    for seg in ("C_1", "O", "P_1", "Q_1"):
        assert rm.get_data(f"verification/{seg}/verified_hits") is None, (
            f"{seg} has partial-group verification")
    # the cut is reported
    assert any(code == "stage_time_budget" for code, _ in ctx.warnings)
    assert out.summary.get("partial") is True
