"""OQ-11 (2026-10-05): local ChEMBL mirror formula resolver.

EBI ChEMBL REST dropped formula support (payloads carry no formula fields;
the coded exact filter HTTP-400-swallow-soft-fails). The resolver now does
a local sqlite lookup first (chembl.local_db_path on the databases PVC)
and only degrades to the legacy REST path — with one warning — when the
mirror is absent. Lookup contract preserved: exact formula, deduped
ascending list, 200 cap. Content uses a tiny hand-built sqlite so no
network is touched anywhere.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.formula import FormulaChEMBLResolver
from src_new.molecules.chembl_db import ChEMBLDB


def _mk_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE chembl_compounds (chembl_id TEXT PRIMARY KEY, formula TEXT NOT NULL)"
    )
    rows = [
        ("CHEMBL25", "C9H8O4"),
        ("CHEMBL113", "C8H10N4O2"),
        ("CHEMBL2107105", "C8H10N4O2"),  # same formula, must both appear, ordered
        ("CHEMBL6329", "C5H8O2N2"),
    ]
    conn.executemany("INSERT INTO chembl_compounds VALUES (?, ?)", rows)
    conn.execute("CREATE INDEX idx_formula ON chembl_compounds(formula)")
    conn.commit()
    conn.close()


def _config(db_path: str) -> RunConfig:
    cfg = RunConfig()
    cfg.identifiers.formula_chembl = True
    cfg.chembl.local_db_path = str(db_path)
    return cfg


def test_db_by_formula_orders_and_dedupes(tmp_path: Path) -> None:
    db_file = tmp_path / "chembl.sqlite"
    _mk_db(db_file)
    db = ChEMBLDB(db_file)
    assert db.exists()
    hits = db.by_formula("C8H10N4O2")
    assert hits == ["CHEMBL113", "CHEMBL2107105"]  # ascending numeric
    assert db.by_formula("C9H8O4") == ["CHEMBL25"]
    assert db.by_formula("C999H999") == []
    assert db.by_formula("") == []


def test_db_exists_false_when_absent(tmp_path: Path) -> None:
    db = ChEMBLDB(tmp_path / "nope.sqlite")
    assert db.exists() is False


def test_resolver_prefers_local_no_network(tmp_path: Path) -> None:
    db_file = tmp_path / "chembl.sqlite"
    _mk_db(db_file)
    r = FormulaChEMBLResolver(_config(str(db_file)))
    r._session = MagicMock()  # MUST never be called when mirror is present
    hits = r.resolve("C8H10N4O2", as_similarity=False)
    assert hits == ["CHEMBL113", "CHEMBL2107105"]
    r._session.get.assert_not_called()


def test_resolver_degrades_to_rest_with_warning(tmp_path: Path, caplog) -> None:
    cfg = _config(str(tmp_path / "absent.sqlite"))
    r = FormulaChEMBLResolver(cfg)
    assert "mirror DB missing" in caplog.text
    # legacy REST path: 400 -> soft-empty (upstream dead), session called
    session = MagicMock()
    resp = MagicMock()
    resp.status_code = 400
    import requests
    err = requests.HTTPError(response=resp)
    resp.raise_for_status = MagicMock(side_effect=err)
    session.get.return_value = resp
    r._session = session
    assert r.resolve("C8H10N4O2", as_similarity=False) == []
    assert session.get.called


def test_similarity_still_unapplicable(tmp_path: Path) -> None:
    db_file = tmp_path / "chembl.sqlite"
    _mk_db(db_file)
    r = FormulaChEMBLResolver(_config(str(db_file)))
    assert r.resolve("C8H10N4O2", as_similarity=True) == []
