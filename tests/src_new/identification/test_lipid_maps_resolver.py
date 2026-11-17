"""LIPID MAPS lookup by lipid species (resolvers/lipid.py).

The chain-resolved shorthand ('PC(16:0/18:1(9Z))') contains "/", which LMSD's
REST paths reject with 404 even URL-encoded: the lookup never found an
acyl-specific lipid (2026-11-17)."""
from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolutionError
from src_new.identification.resolvers.lipid import (LipidShorthandResolver, _lm_ids,
                                                     species_shorthand)


@pytest.mark.parametrize("shorthand,species", [
    ("PC(16:0/18:1(9Z))", "PC 34:1"),
    ("PE(18:1(9Z)/18:1(9Z))", "PE 36:2"),
    ("PC(O-16:0/18:1)", "PC O-34:1"),
    ("SM(d18:1/16:0)", "SM 34:1;O2"),
    ("CL(14:0/14:0/14:0/14:0)", "CL 56:0"),
    ("PI(16:0/20:4(5Z,8Z,11Z,14Z))", "PI 36:4"),
    ("ST 27:1;O", "ST 27:1;O"),
    ("CL", None),
    ("PC(x/y)", None),
])
def test_species_shorthand(shorthand, species):
    assert species_shorthand(shorthand) == species


def test_lm_ids_shapes():
    assert _lm_ids({"input": "PC 34:1", "lm_id": "LMGP01010005"}) == ["LMGP01010005"]
    assert _lm_ids({"Row1": {"lm_id": "A"}, "Row2": {"lm_id": "B"}}) == ["A", "B"]
    assert _lm_ids([]) == []


class Resp:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_resolver_queries_the_species_and_caps(monkeypatch):
    r = LipidShorthandResolver(RunConfig())
    urls = []
    rows = {f"Row{i}": {"lm_id": f"LMGP{i:08d}"} for i in range(40)}
    monkeypatch.setattr(r._session, "get", lambda url, timeout: urls.append(url) or Resp(200, rows))
    ids = r._resolve_identity("PC(16:0/18:1(9Z))", "/tmp")
    assert urls == ["https://www.lipidmaps.org/rest/compound/abbrev/PC%2034%3A1/lm_id"]
    assert len(ids) == 25 and ids[0] == "LMGP00000000"
    monkeypatch.setattr(r._session, "get", lambda url, timeout: Resp(404))
    assert r._resolve_identity("PC(16:0/18:1)", "/tmp") == []
    assert r._resolve_identity("CL", "/tmp") == []  # bare class: nothing to ask
    monkeypatch.setattr(r._session, "get", lambda url, timeout: Resp(503))
    with pytest.raises(IdentifierResolutionError):
        r._resolve_identity("PC(16:0/18:1)", "/tmp")
