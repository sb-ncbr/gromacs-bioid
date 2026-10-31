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
