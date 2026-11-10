"""Shared fixtures for the src_new test tree.

W3.2 A7: the signature fetchers memoize results in a module-level,
run-scoped memo (see src_new/verification/base.py — production burns
~5 min per repeated key on the firewalled workstation). The memo is
cleared at each verify_results stage start in production; in the test
suite many "runs" share one process, so clear it between tests to keep
fetcher tests isolated (e.g. two tests mocking the same PDB id with
different responses must not see each other's memoized value).
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_fetch_run_memo():
    from src_new.verification.base import clear_run_memo
    clear_run_memo()
    yield
    clear_run_memo()


@pytest.fixture(autouse=True)
def _clear_dbo_reuse():
    """c13 D1: bond-order reuse is per run (run id set at the
    generate_signatures stage start, which also clears it). Tests share a
    process, so neither a run id set by a pipeline test nor its memo may
    leak into the next test."""
    from src_new.signatures.generators import _perceive_cache as pc
    pc.set_dbo_run_id(None)
    pc._dbo_memo.clear()
    yield
    pc.set_dbo_run_id(None)
    pc._dbo_memo.clear()


@pytest.fixture(autouse=True)
def _no_traffic_recording(monkeypatch):
    """Traffic statistics (src_new/api/traffic.py) stay off in tests, and the
    GeoIP database is never downloaded; test_traffic.py turns recording on."""
    monkeypatch.setenv("BAT3_TRAFFIC", "0")
    monkeypatch.setenv("BAT3_GEOIP_REFRESH", "0")
