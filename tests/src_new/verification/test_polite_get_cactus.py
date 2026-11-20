"""_polite_get and CACTUS's 'not found' 500s (2026-11-20). No network."""
from __future__ import annotations

from types import SimpleNamespace

from src_new.verification.fetchers import compound_fetcher as mod

URL = "https://cactus.nci.nih.gov/chemical/structure/MQWPNAKTHWSSMC-BGIGGGFGSA-N/smiles"


def _serve(monkeypatch, *responses):
    calls = []

    def get(url, timeout=None):
        calls.append(url)
        return responses[min(len(calls), len(responses)) - 1]
    monkeypatch.setattr(mod.requests, "get", get)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    return calls


def test_cactus_unknown_key_is_not_retried(monkeypatch):
    calls = _serve(monkeypatch, SimpleNamespace(status_code=500, text="<h1>Page not found (404)</h1>"))
    assert mod._polite_get(URL) is None
    assert len(calls) == 1


def test_a_real_server_error_is_still_retried(monkeypatch):
    ok = SimpleNamespace(status_code=200, text="CCO", raise_for_status=lambda: None)
    calls = _serve(monkeypatch, SimpleNamespace(status_code=500, text="<h1>Server Error (500)</h1>"), ok)
    assert mod._polite_get(URL) is ok
    assert len(calls) == 2
