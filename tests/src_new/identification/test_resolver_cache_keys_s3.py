"""c13 S3: long signatures are cached under a sha256 key, not the full text.

b14 fleet 2026-11-04: the SIGNATURE column held each 100-400 KB structure
signature once per RCSB hit (7,146 pdb_struct_protein rows from 3 query
structures = 1.7 GB in 26 min) and the 2 GiB pod-local emptyDir evicted
the worker.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.cache_manager import (
    ResolverCache, _signature_key, create_empty_cache_if_not_exists)

_STRUCTURE = "".join(
    f"ATOM  {i:5d}  CA  ALA A{i:4d}    {i:8.3f}   0.000   0.000  1.00  0.00           C\n"
    for i in range(1, 4001))  # ~320 KB, a mid-size structure signature


@pytest.fixture
def config(tmp_path: Path) -> RunConfig:
    cfg = RunConfig()
    cfg.identifiers_cache.directory = str(tmp_path)
    cfg.identifiers_cache.file = "cache.sqlite3"
    return cfg


def test_many_structure_hits_stay_small(config, tmp_path):
    cache = ResolverCache(config)
    hits = [(f"{i:04d}", 0.5) for i in range(2000)]
    cache.save_similarity_identifiers("pdb_struct_protein", _STRUCTURE, hits)
    assert sorted(cache.fetch_similarity_identifiers(
        "pdb_struct_protein", _STRUCTURE)) == sorted(hits)
    cache._conn.close()
    size = os.path.getsize(tmp_path / "cache.sqlite3")
    assert size < 2 * 1024 * 1024, f"{size} bytes for 2,000 hits"


def test_long_signature_stored_as_hash_key(config, tmp_path):
    cache = ResolverCache(config)
    cache.save_identity_identifiers("mmcif_struct", _STRUCTURE, ["1N8U"])
    cache.save_similarity_identifiers("mmcif_struct", _STRUCTURE, [("1KX8", 0.9)])
    assert cache.fetch_identity_identifiers("mmcif_struct", _STRUCTURE) == ["1N8U"]
    assert cache.fetch_similarity_identifiers("mmcif_struct", _STRUCTURE) == [("1KX8", 0.9)]
    stored = {row[0] for t in ("CACHE_IDENTITY", "CACHE_SIMILARITY")
              for row in cache._conn.execute(f"SELECT SIGNATURE FROM {t}")}
    assert stored == {_signature_key(_STRUCTURE)}
    assert all(s.startswith("sha256:") and len(s) == 71 for s in stored)


def test_short_signature_key_unchanged(config):
    cache = ResolverCache(config)
    cache.save_similarity_identifiers("blast_pdb_protein", "MKTAYIAK", [("1ABC", 0.8)])
    assert [r[0] for r in cache._conn.execute(
        "SELECT SIGNATURE FROM CACHE_SIMILARITY")] == ["MKTAYIAK"]
    assert _signature_key("CCO") == "CCO"


def test_pre_s3_full_text_rows_still_hit(config, tmp_path):
    """Warm-start seed rows were written with the full signature text."""
    path = str(tmp_path / "cache.sqlite3")
    create_empty_cache_if_not_exists(path)
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO CACHE_SIMILARITY VALUES (?, ?, ?, ?)",
                     ("foldseek", _STRUCTURE, "AF-P12345-F1", 0.7))
        conn.execute("INSERT INTO CACHE_IDENTITY VALUES (?, ?, ?)",
                     ("foldseek", _STRUCTURE, "AF-P12345-F1"))
    cache = ResolverCache(config)
    assert cache.fetch_similarity_identifiers("foldseek", _STRUCTURE) == [("AF-P12345-F1", 0.7)]
    assert cache.fetch_identity_identifiers("foldseek", _STRUCTURE) == ["AF-P12345-F1"]
    # saving the same hit again must not duplicate it under the new key
    cache.save_similarity_identifiers("foldseek", _STRUCTURE, [("AF-P12345-F1", 0.7)])
    assert cache._conn.execute("SELECT COUNT(*) FROM CACHE_SIMILARITY").fetchone()[0] == 1
