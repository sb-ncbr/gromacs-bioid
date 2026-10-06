"""OQ-13 (2026-10-06): resolver-cache corruption resilience.

Live incident class: a corrupt cache file surfaced sqlite3.DatabaseError
'file is not a database' out of EVERY cache-using resolve() call, killing
identification for any pod holding the poisoned file (UI lane pinned to 2
pods -> 100% UI-lane failure). The shared-NFS relic even has a
.corrupt-20260910 sibling proving recurrence.

Fixes under test:
1. cache_manager._connection probes integrity at open; corrupt file is
   quarantined aside (never deleted) and recreated empty - self-heal.
2. base.resolve guards cache read/write with sqlite3.Error -> degrades to
   cache-miss / uncached-result; live resolution never dies from cache rot.
"""
from __future__ import annotations

import glob
import os
import sqlite3
from pathlib import Path

from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolver
from src_new.identification.cache_manager import ResolverCache


def _config(cache_dir: Path) -> RunConfig:
    cfg = RunConfig()
    cfg.identifiers_cache.directory = str(cache_dir)
    cfg.identifiers_cache.file = "test_cache.sqlite3"
    return cfg


class _DummyResolver(IdentifierResolver):
    """Minimal concrete resolver: identity returns a fixed hit."""

    @property
    def name(self) -> str:
        return "dummy"

    def _is_applicable(self, signature: str) -> bool:
        return True

    def _resolve_identity(self, signature: str, working_directory: str = ""):
        return ["DUMMY-HIT"]

    def _resolve_similarity(self, signature: str, working_directory: str = ""):
        return [("DUMMY-HIT", 100.0)]


def _corrupt_file(path: Path) -> None:
    path.write_bytes(b"this is definitely not a sqlite header" + b"\x00" * 512)


def test_corrupt_cache_selfheals_and_quarantines(tmp_path: Path) -> None:
    cache_file = tmp_path / "test_cache.sqlite3"
    _corrupt_file(cache_file)

    cache = ResolverCache(_config(tmp_path))
    cached = cache.fetch_identity_identifiers("dummy", "sig-1")
    assert cached == []

    # Self-healed: fresh valid sqlite now parses and is usable
    with sqlite3.connect(cache_file) as conn:
        assert conn.execute("SELECT count(*) FROM CACHE_IDENTITY").fetchone()[0] == 0

    # Corrupt original was quarantined aside, NOT deleted
    asides = glob.glob(str(cache_file) + ".corrupt-*")
    assert len(asides) == 1
    assert os.path.getsize(asides[0]) > 500


def test_healthy_cache_roundtrip_unchanged(tmp_path: Path) -> None:
    cache = ResolverCache(_config(tmp_path))
    cache.save_identity_identifiers("dummy", "sig-2", ["HIT-1", "HIT-2"])
    assert set(cache.fetch_identity_identifiers("dummy", "sig-2")) == {"HIT-1", "HIT-2"}


def test_resolve_survives_corrupt_cache_and_recovers(tmp_path: Path) -> None:
    cache_file = tmp_path / "test_cache.sqlite3"
    _corrupt_file(cache_file)

    resolver = _DummyResolver(_config(tmp_path))
    cache = ResolverCache(_config(tmp_path))  # self-heal happens here too
    # Re-poison AFTER open so the fetch itself hits the live guard path:
    # an already-open connection that later goes corrupt must degrade, not die.
    conn = cache._connection
    conn.execute("DROP TABLE CACHE_IDENTITY")
    conn.commit()  # now reads raise OperationalError inside fetch -> guarded

    out = resolver.resolve("sig-3", as_similarity=False, cache=cache)
    assert out == ["DUMMY-HIT"]


def test_similarity_resolution_survives_broken_cache_table(tmp_path: Path) -> None:
    cache = ResolverCache(_config(tmp_path))
    conn = cache._connection
    conn.execute("DROP TABLE CACHE_SIMILARITY")
    conn.commit()

    resolver = _DummyResolver(_config(tmp_path))
    out = resolver.resolve("sig-4", as_similarity=True, cache=cache)
    assert out == [("DUMMY-HIT", 100.0)]
