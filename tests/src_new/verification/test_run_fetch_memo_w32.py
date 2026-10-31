"""W3.2 A7: run-scoped fetch memo for signature fetchers.

Production evidence (W3 package, P23 results.log): the same InChIKey
(XUVWGNKSYIFPIN-UHFFFAOYSA-N) was fetched over the network 3 times,
~5 min per attempt on the firewalled workstation — once per segment
that mentioned it. Fetch results (INCLUDING negative results: an
unresolvable key stays unresolvable within the run) are memoized per
(fetcher class, ident type, identifier) for the lifetime of one run,
and the memo is cleared at each verify_results stage start.
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest

from src_new.verification.base import SignatureFetcher, clear_run_memo, memoized_fetch


@pytest.fixture(autouse=True)
def _clean_memo():
    clear_run_memo()
    yield
    clear_run_memo()


def _fetcher(value="SMILES"):
    class F(SignatureFetcher):
        def __init__(self):
            self.calls = 0

        def supports(self, ident_type):
            return True

        @memoized_fetch
        def fetch(self, identifier, ident_type):
            self.calls += 1
            return value

    return F()


def test_hit_within_run_counts_once():
    f = _fetcher("SMILES")
    assert f.fetch("XUVWGNKSYIFPIN-UHFFFAOYSA-N", "INCHIKEY") == "SMILES"
    assert f.fetch("XUVWGNKSYIFPIN-UHFFFAOYSA-N", "INCHIKEY") == "SMILES"
    assert f.calls == 1, "second fetch of the same key hit the network again"


def test_negative_results_are_memoized():
    f = _fetcher(None)  # unresolved (firewalled / unknown)
    assert f.fetch("XUVWGNKSYIFPIN-UHFFFAOYSA-N", "INCHIKEY") is None
    assert f.fetch("XUVWGNKSYIFPIN-UHFFFAOYSA-N", "INCHIKEY") is None
    assert f.calls == 1, "an unresolved key was re-fetched within the run"


def test_keys_are_typed_and_clear_resets():
    class F(SignatureFetcher):
        def __init__(self):
            self.calls = 0

        def supports(self, ident_type):
            return True

        @memoized_fetch
        def fetch(self, identifier, ident_type):
            self.calls += 1
            return f"v{self.calls}"

    f = F()
    assert f.fetch("P01308", "UNIPROT_ID") == "v1"
    # same identifier under a different ident type: separate memo key
    assert f.fetch("P01308", "PDB_ID") == "v2"
    # different fetcher class: separate memo key (sequence vs structure)
    g = F()
    assert g.fetch("P01308", "UNIPROT_ID") == "v1"  # fresh instance, same class
    clear_run_memo()
    assert f.fetch("P01308", "UNIPROT_ID") == "v3"


def test_verify_stage_clears_the_memo(tmp_path):
    """_verify_results starts with a fresh memo (per-run semantics even
    when several runs share one process — e.g. the test suite)."""
    import json
    from src_new.config.loader import RunConfig
    from src_new.pipeline_steps import _verify_results
    from src_new.results.results_manager import ResultsManager
    import src_new.verification.base as base_mod

    class _Ctx:
        def __init__(self, results, config):
            self.results = results
            self.config = config
            self.warnings = []

        def get_value(self, key):
            return object() if key == "facade" else None

        def fail(self, code, msg):
            raise AssertionError(code)

        def add_warning(self, code, msg):
            self.warnings.append((code, msg))

    p = tmp_path / "results.json"
    p.write_text(json.dumps({"pipeline_name": "t", "data": {}}))
    rm = ResultsManager(str(p), pipeline_name="t")
    rm.set_data("identifiers", {})  # no segments -> early, memo-free path
    cfg = RunConfig()
    cfg.executor.verification_parallel = False

    base_mod.run_memo_put(("StaleFetcher", "INCHIKEY", "STALE"), "stale")
    _verify_results(_Ctx(rm, cfg))
    assert base_mod.run_memo_get(("StaleFetcher", "INCHIKEY", "STALE")) \
        is base_mod._MEMO_MISS, "verify_results did not start with a clean memo"
