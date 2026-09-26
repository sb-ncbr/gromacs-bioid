"""F15 mirror block-range structure fetch tests (WAVE 5).

The fragment's own InChIKey is often a stereo/protonation variant of the
mirrored compound; an exact-key miss must fall back to the shared
connectivity block (skeleton comparisons are stereo/H-insensitive).
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from unittest.mock import MagicMock

from src_new.molecules.pubchem_db import SCHEMA, PubChemDB


BLOCK = "UCJCNZJAAQBBMU"
ROWS = [
    (100, "CC(=O)Oc1ccccc1C(=O)O", f"{BLOCK}-UHFFFAOYSA-N", "C9H8O4", 180.16),
    (200, "O", "XXXXXXXXXXXXXX-UHFFFAOYSA-N", "H2O", 18.01),
]


def _make_db(tmp_path):
    path = tmp_path / "pubchem.sqlite"
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.execute("CREATE INDEX IF NOT EXISTS idx_inchikey ON compounds(inchikey)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_formula ON compounds(formula_hill)")
    for r in ROWS:
        con.execute(
            "INSERT INTO compounds (cid, smiles, inchikey, formula_hill, exact_mass)"
            " VALUES (?,?,?,?,?)", r)
    con.commit()
    con.close()
    return str(path)


class TestByInchikeyBlock:
    def test_block_resolves_variant_key(self, tmp_path):
        db = PubChemDB(_make_db(tmp_path))
        # query a stereo variant key absent from the table
        row = db.by_inchikey_block(f"{BLOCK}-SWGQDTFXSA-N")
        assert row is not None
        assert row.cid == 100
        assert row.smiles.startswith("CC(=O)O")

    def test_exact_miss_other_block_returns_none(self, tmp_path):
        db = PubChemDB(_make_db(tmp_path))
        assert db.by_inchikey_block("ZZZZZZZZZZZZZZ-UHFFFAOYSA-N") is None
        assert db.by_inchikey_block("") is None


class TestFetcherBlockFallback:
    def _fetcher(self, db):
        from src_new.verification.fetchers import compound_fetcher as mod
        fetcher = mod.CompoundSignatureFetcher()
        return mod, fetcher

    def test_exact_miss_falls_back_to_block_no_http(self, tmp_path, monkeypatch):
        from src_new.verification.fetchers import compound_fetcher as mod
        real_db = PubChemDB(_make_db(tmp_path))
        monkeypatch.setattr(mod, "_local_db", lambda: real_db)
        monkeypatch.setattr(mod, "_cache_read_ns", lambda ns, ident: None)
        monkeypatch.setattr(mod, "_cache_write_ns", lambda ns, ident, val: None)
        fetcher = mod.CompoundSignatureFetcher()
        called = []
        monkeypatch.setattr(mod, "_polite_get",
                            lambda url: (called.append(url), None)[1])
        smi = fetcher._fetch_inchikey(f"{BLOCK}-SWGQDTFXSA-N")
        assert smi == "CC(=O)Oc1ccccc1C(=O)O"
        assert called == []          # no HTTP at all

    def test_unknown_key_still_falls_to_network(self, tmp_path, monkeypatch):
        from src_new.verification.fetchers import compound_fetcher as mod
        real_db = PubChemDB(_make_db(tmp_path))
        monkeypatch.setattr(mod, "_local_db", lambda: real_db)
        monkeypatch.setattr(mod, "_cache_read_ns", lambda ns, ident: None)
        monkeypatch.setattr(mod, "_cache_write_ns", lambda ns, ident, val: None)
        fetcher = mod.CompoundSignatureFetcher()
        called = []
        monkeypatch.setattr(mod, "_polite_get",
                            lambda url: (called.append(url), None)[1])
        smi = fetcher._fetch_inchikey("ZZZZZZZZZZZZZZ-UHFFFAOYSA-N")
        assert smi is None
        assert called                # network fallbacks attempted
