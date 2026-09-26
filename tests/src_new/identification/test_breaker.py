"""PubChem circuit breaker tests (no network)."""

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from unittest.mock import MagicMock

import src_new.identification.resolution_manager as rm


def _pubchem_resolver():
    r = MagicMock()
    r.name = "formula_pubchem"
    return r


def _chembl_resolver():
    r = MagicMock()
    r.name = "idsm_chembl"
    return r


def test_blocked_when_unhealthy(monkeypatch):
    monkeypatch.setattr(rm, "_pubchem_healthy", lambda: False)
    assert True
    pug = _pubchem_resolver()
    # emulate the loop condition
    blocked = lambda r: (not rm._pubchem_healthy()) and (r.name in rm._PUBCHEM_RESOLVERS)
    assert blocked(pug) is True
    ch = _chembl_resolver()
    assert blocked(ch) is False         # ChEMBL unaffected


def test_passes_when_healthy(monkeypatch):
    monkeypatch.setattr(rm, "_pubchem_healthy", lambda: True)
    blocked = lambda r: (not rm._pubchem_healthy()) and (r.name in rm._PUBCHEM_RESOLVERS)
    assert blocked(_pubchem_resolver()) is False


def test_env_override_disables_breaker(monkeypatch):
    monkeypatch.setenv("VALIDATION_PUBCHEM_BREAKER", "0")
    monkeypatch.setattr(rm, "_probe_state", {"ts": 0.0, "healthy": False})
    assert rm._pubchem_healthy() is True   # override forces healthy regardless of state


def test_module_helper_blocks_pubchem_when_unhealthy(monkeypatch):
    monkeypatch.setattr(rm, "_pubchem_healthy", lambda: False)
    pug = _pubchem_resolver()
    del pug.offline_capable   # real resolvers lack the attribute: getattr -> None
    assert rm._breaker_blocked(pug, False) is True
    ch = _chembl_resolver()
    del ch.offline_capable
    assert rm._breaker_blocked(ch, False) is False


def test_module_helper_offline_capable_resolver_not_blocked():
    r = MagicMock()
    r.name = "formula_hfamily"
    r.offline_capable = lambda: True
    assert rm._breaker_blocked(r, False) is False


def test_module_helper_offline_capable_false_stays_blocked():
    r = MagicMock()
    r.name = "formula_hfamily"
    r.offline_capable = lambda: False
    assert rm._breaker_blocked(r, False) is True


def test_module_helper_offline_check_raises_falls_back_to_blocked():
    r = MagicMock()
    r.name = "formula_hfamily"
    def _boom():
        raise RuntimeError("db gone")
    r.offline_capable = _boom
    assert rm._breaker_blocked(r, False) is True


def test_module_helper_healthy_never_blocks():
    r = MagicMock()
    r.name = "formula_pubchem"
    assert rm._breaker_blocked(r, True) is False
