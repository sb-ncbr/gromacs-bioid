"""BH-054 regression: ResolverCache init under a concurrent writer.

`PRAGMA journal_mode=WAL` returns SQLITE_BUSY immediately when another
connection holds a write lock — SQLite does not invoke the busy handler
for this pragma. Before BH-054 the lazy-init exception hit
`_get_connection`'s blanket except, permanently disabling the cache
(`_disabled = True`) for the losing run: exactly the production
"[Cache] disabled" failure mode of a shared resolver cache initialized
by two concurrent runs.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from src_new.config.loader import RunConfig
from src_new.identification.cache_manager import (
    ResolverCache,
    create_empty_cache_if_not_exists,
)


def _make_config(cache_dir: Path) -> RunConfig:
    config = RunConfig()
    config.identifiers_cache.directory = str(cache_dir)
    config.identifiers_cache.file = "test_cache.sqlite3"
    return config


def test_init_under_concurrent_writer_does_not_disable_cache(tmp_path: Path) -> None:
    """A write lock held at init must not permanently disable the cache.

    Deterministic BH-054 repro: hold an open write transaction on the
    shared cache file (a concurrent run mid-INSERT), then lazy-init a
    ResolverCache — the WAL switch fails instantly with "database is
    locked" and must be tolerated, not fatal.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "test_cache.sqlite3"
    create_empty_cache_if_not_exists(str(cache_file))

    # A concurrent run holding a pending write transaction
    blocker = sqlite3.connect(str(cache_file), timeout=30.0)
    blocker.execute("BEGIN")
    blocker.execute("INSERT INTO CACHE_IDENTITY VALUES ('r', 's', 'i')")

    cache = ResolverCache(_make_config(cache_dir))
    # Lazy init happens under the write lock
    conn = cache._connection
    assert conn is not None, "cache must produce a connection"
    assert not cache._disabled, (
        "transient 'database is locked' during init permanently disabled "
        "the cache (BH-054)"
    )

    # Release the writer, then the cache must be fully functional
    blocker.rollback()
    blocker.close()
    cache.save_identity_identifiers("resolver_x", "sig_x", ["id_1", "id_2"])
    results = cache.fetch_identity_identifiers("resolver_x", "sig_x")
    assert len(results) == 2
    assert not cache._disabled


def test_create_empty_cache_concurrent_init_is_idempotent(tmp_path: Path) -> None:
    """TOCTOU twin of BH-054: N threads racing the empty-cache creation
    must all succeed (CREATE TABLE IF NOT EXISTS), none may raise."""
    cache_file = tmp_path / "race" / "test_cache.sqlite3"
    (tmp_path / "race").mkdir()

    errors: list[Exception] = []

    def create() -> None:
        try:
            create_empty_cache_if_not_exists(str(cache_file))
        except Exception as exc:  # pragma: no cover - only on failure
            errors.append(exc)

    threads = [threading.Thread(target=create) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent cache creation raised: {errors}"

    # The created file must be a valid, populated cache
    cache = ResolverCache(_make_config(tmp_path / "race"))
    cache.save_identity_identifiers("r", "s", ["x"])
    assert cache.fetch_identity_identifiers("r", "s") == ["x"]
