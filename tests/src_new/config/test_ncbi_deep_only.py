"""NCBI nr / nt / core_nt: Deep search only, with their own 12 h limit (2026-11-18)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from src_new.config.loader import RunConfig
from src_new.config.presets import resolve_run_config
from src_new.pipeline_steps import NCBI_DATABASES, ncbi_extension_s, set_stage_budget

SWITCHES = [k for n in NCBI_DATABASES for k in (n, f"{n}_similarity")]


@pytest.mark.parametrize("preset", [None, "balanced", "quick", "exact"])
def test_off_outside_deep(preset):
    ids = resolve_run_config(preset, None).identifiers
    assert not any(getattr(ids, k) for k in SWITCHES)
    assert ncbi_extension_s(resolve_run_config(preset, None)) == 0


def test_on_in_deep():
    config = resolve_run_config("deep", None)
    assert all(getattr(config.identifiers, k) for k in SWITCHES)
    assert config.blast.ncbi_timeout_s == 12 * 3600
    assert ncbi_extension_s(config) == 12 * 3600


def test_one_switch_is_enough():
    config = resolve_run_config(None, None)
    config.identifiers.blast_nt_similarity = True
    assert ncbi_extension_s(config) == config.blast.ncbi_timeout_s


def test_ncbi_resolvers_use_their_own_limit():
    from src_new.identification.resolvers.blast import (
        BLASTResolverCORENT, BLASTResolverNR, BLASTResolverNT,
        BLASTResolverPDBAA, BLASTResolverUNIREF50)
    config = RunConfig.from_default_ini()
    for cls in (BLASTResolverNR, BLASTResolverNT, BLASTResolverCORENT):
        assert cls(config)._search_timeout_s() == 43200
    assert BLASTResolverPDBAA(config)._search_timeout_s() == config.blast.timeout_s == 3600
    assert BLASTResolverUNIREF50(config)._search_timeout_s() == config.blast.uniref50_timeout_s
    config.blast.ncbi_timeout_s = 0  # unset: the general limit
    assert BLASTResolverNR(config)._search_timeout_s() == 3600


def _deadline(config, step_id, monkeypatch):
    monkeypatch.setenv("VALIDATION_STAGE_BUDGETS", '{"identify_molecules": 4500}')
    ctx = MagicMock()
    ctx.config = config
    set_stage_budget(ctx, step_id)
    return ctx.set_value.call_args[0][1] - time.time()


def test_identify_budget_grows_only_with_ncbi(monkeypatch):
    plain = _deadline(resolve_run_config(None, None), "identify_molecules", monkeypatch)
    deep = _deadline(resolve_run_config("deep", None), "identify_molecules", monkeypatch)
    assert 4490 < plain <= 4500
    assert 4490 + 43200 < deep <= 4500 + 43200
    verify = _deadline(resolve_run_config("deep", None), "verify_results", monkeypatch)
    assert verify <= 1200


def test_run_wall_clock_limit_grows_with_ncbi(tmp_path):
    from src_new.api.tasks import _ncbi_extension_for
    assert _ncbi_extension_for(None) == 0
    deep, balanced = tmp_path / "deep.ini", tmp_path / "balanced.ini"
    resolve_run_config("deep", None).to_ini_path(deep)
    resolve_run_config("balanced", None).to_ini_path(balanced)
    assert _ncbi_extension_for(str(deep)) == 43200
    assert _ncbi_extension_for(str(balanced)) == 0
    assert _ncbi_extension_for(str(tmp_path / "missing.ini")) == 0
