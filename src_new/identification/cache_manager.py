"""Thread-safe SQLite cache for identifier resolution."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import sqlite3
import threading
import time
from datetime import datetime, timezone

from ..config.loader import RunConfig

logger = logging.getLogger("identifier")


def _quarantine_if_corrupt(cache_path: str) -> None:
    """OQ-13 (2026-10-06): integrity-probe an existing cache; corrupt -> quarantine + recreate.

    "file is not a database" historically killed every identification on a
    poisoned pod (cache reads were unguarded), and a stale corrupt relic even
    sat on the shared NFS runs volume (.corrupt-20260910 sibling proves the
    class recurs). Detection is cheap (PRAGMA quick_check at open). A corrupt
    file is NEVER deleted - renamed aside next to the original for forensics,
    then an empty cache is recreated so identification proceeds immediately.
    """
    if not os.path.exists(cache_path):
        return
    try:
        with sqlite3.connect(cache_path, timeout=30.0) as conn:
            verdict = conn.execute("PRAGMA quick_check").fetchone()
        if verdict and str(verdict[0]).lower() == "ok":
            return
    except sqlite3.DatabaseError:
        pass  # header/page corrupt -> quarantine below

    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    aside = f"{cache_path}.corrupt-{ts}"
    logger.error(
        "[Cache] resolver cache at '%s' is corrupt ('file is not a database' class); "
        "quarantining to '%s' and recreating empty (OQ-13 self-heal)",
        cache_path, aside,
    )
    try:
        os.replace(cache_path, aside)
    except OSError as exc:
        logger.error("[Cache] failed to quarantine corrupt cache '%s': %s", cache_path, exc)
        # Leave the file; recreation will fail loudly below if still broken.



def create_empty_cache_if_not_exists(cache_path: str) -> None:
    """Create empty cache database if it doesn't exist.
    
    Args:
        cache_path: Path to the cache database file.
    """
    if os.path.exists(cache_path):
        return

    logger.warning(f"[Cache] Resolver cache not found at '{cache_path}': Initializing empty")

    directory_path: str = os.path.dirname(cache_path)
    if directory_path and not os.path.exists(directory_path):
        os.makedirs(directory_path)

    with sqlite3.connect(cache_path, timeout=30.0) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS "CACHE_IDENTITY" (
                        "RESOLVER_NAME"	TEXT NOT NULL,
                        "SIGNATURE"	    TEXT NOT NULL,
                        "IDENTIFIER"	TEXT NOT NULL,
                        PRIMARY KEY("IDENTIFIER","SIGNATURE","RESOLVER_NAME"));
                    """
        )

        conn.execute(
            """CREATE TABLE IF NOT EXISTS "CACHE_SIMILARITY" (
                        "RESOLVER_NAME"	TEXT NOT NULL,
                        "SIGNATURE"	    TEXT NOT NULL,
                        "IDENTIFIER"	TEXT NOT NULL,
                        "SIMILARITY"	REAL,
                        PRIMARY KEY("IDENTIFIER","SIGNATURE","RESOLVER_NAME"));
                    """
        )

        conn.commit()


# ---------------------------------------------------------------------
# W3.3 corpus run (A.3 health record): per-resolver cache hit/miss
# counters. Purely additive observability — no cache behavior changes.
# The identification step persists `cache_stats_snapshot()` under
# identification/_meta so every results.json carries its own cache
# provenance (hit/miss per resolver + cache read errors).
# ---------------------------------------------------------------------
_STATS_LOCK = threading.RLock()
_CACHE_STATS: dict[str, dict[str, int]] = {}


def record_cache_event(resolver_name: str, hit: bool, *, error: bool = False) -> None:
    """Count one cache lookup outcome for `resolver_name`."""
    with _STATS_LOCK:
        row = _CACHE_STATS.setdefault(
            resolver_name, {"hit": 0, "miss": 0, "error": 0})
        if error:
            row["error"] += 1
        elif hit:
            row["hit"] += 1
        else:
            row["miss"] += 1


def cache_stats_snapshot() -> dict[str, dict[str, int]]:
    """Deep copy of the per-resolver counters (safe to persist)."""
    with _STATS_LOCK:
        return {name: dict(row) for name, row in _CACHE_STATS.items()}


def reset_cache_stats() -> None:
    """Clear the counters (called once per run at identification start so
    each results.json's snapshot is per-run, not per-worker-process)."""
    with _STATS_LOCK:
        _CACHE_STATS.clear()


# c13 S3: the SIGNATURE column used to hold the full signature text, once
# per cached hit and again in the primary-key index. Structure signatures
# are 100-400 KB and RCSB structure search returns thousands of hits per
# query: b14 fleet 2026-11-04, 7,146 pdb_struct_protein rows from 3 query
# structures = 1.7 GB, mmcif_struct 2,491 rows from 1 = 554 MB; the pod-local
# 2 GiB emptyDir evicted the worker mid-run (also q4jc5/r87nt on 9227).
# Long signatures are now stored under a sha256 key; lookups fall back to
# the full text so pre-S3 rows (the warm-start seed) still hit.
_SIGNATURE_HASH_MIN_LEN = 256


def _signature_key(signature: str) -> str:
    if len(signature) < _SIGNATURE_HASH_MIN_LEN:
        return signature
    return "sha256:" + hashlib.sha256(signature.encode("utf-8")).hexdigest()


class ResolverCache:
    """Thread-safe SQLite cache for identifier resolution results.
    
    Uses RLock for thread safety and lazy connection initialization.
    """

    
    def __init__(self, config: RunConfig) -> None:
        """Initialize resolver cache.
        
        Args:
            config: RunConfig containing cache path configuration.
        """
        self._config = config
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        self._cache_path: str | None = None
        # v3.143 (C-13): after the first init failure (unwritable/missing
        # directory) the cache goes no-op — log once, never retry the
        # connect on every call (was: exception on EVERY resolver).
        self._disabled: bool = False
    
    def _get_connection(self) -> sqlite3.Connection | None:
        """Connection or None when the cache is disabled (v3.143, C-13)."""
        if self._disabled:
            return None
        try:
            return self._connection
        except (OSError, sqlite3.Error) as exc:
            if not self._disabled:
                self._disabled = True
                logger.warning(
                    "[Cache] disabled after initialization failure (%s); "
                    "resolvers continue without cache", exc)
            return None

    @property
    def _connection(self) -> sqlite3.Connection:
        """Lazy connection initialization."""
        if self._disabled:
            raise OSError("cache disabled after prior initialization failure")
        if self._conn is None:
            # BH-048 (W3 A7): an empty directory resolved as
            # "./resolver_cache.sqlite3" in the container's UNWRITABLE cwd,
            # silently disabling the cache in ~80% of production runs.
            # Fall back to a writable location instead of dying open.
            # UI pass 2026-11-07: the deployment's own cache directory wins.
            # API-created run configs carried directory=/app/runs (the shared
            # NFS volume), so both UI workers wrote ONE SQLite file in WAL
            # mode over NFS — unsupported by SQLite: it was corrupted and
            # quarantined repeatedly and runs died with "disk I/O error" and
            # SIGBUS (1KX5 nucleosome, twice). Workers set
            # BAT3_IDENTIFIERS_CACHE_DIR to a pod-local emptyDir.
            cache_directory: str = (os.environ.get("BAT3_IDENTIFIERS_CACHE_DIR", "")
                                    or self._config.identifiers_cache.directory)
            if not cache_directory:
                cache_directory = os.path.join(
                    tempfile.gettempdir(), "bat3_resolver_cache")
                logger.info(
                    "[Cache] identifiers_cache.directory empty; using "
                    "writable fallback %s", cache_directory)
            if not cache_directory.startswith("/"):  # relative = cwd roulette
                fallback = os.path.join(
                    tempfile.gettempdir(), "bat3_resolver_cache")
                logger.warning(
                    "[Cache] relative identifiers_cache.directory %r is not "
                    "portable across workers; using %s",
                    cache_directory, fallback)
                cache_directory = fallback
            os.makedirs(cache_directory, exist_ok=True)
            cache_file: str = self._config.identifiers_cache.file
            self._cache_path = os.path.join(cache_directory, cache_file)

            _quarantine_if_corrupt(self._cache_path)
            create_empty_cache_if_not_exists(self._cache_path)
            self._conn = sqlite3.connect(self._cache_path, timeout=30.0)
            # Enable WAL mode for better concurrent access.
            # BH-054: the WAL switch is best-effort. PRAGMA
            # journal_mode=WAL returns SQLITE_BUSY immediately when
            # another connection holds a write lock (the busy timeout
            # does NOT apply to this pragma) — e.g. a concurrent run
            # initializing the same shared cache. A transient lock here
            # must never disable the cache: read the current mode
            # first, retry the switch a few times, and otherwise
            # continue in the current journal mode (still correct, just
            # serialized). Permanent disable stays reserved for real
            # open/corruption failures.
            mode_row = self._conn.execute("PRAGMA journal_mode").fetchone()
            if mode_row and str(mode_row[0]).lower() != "wal":
                for attempt in range(5):
                    try:
                        self._conn.execute("PRAGMA journal_mode=WAL")
                        break
                    except sqlite3.OperationalError as exc:
                        msg = str(exc).lower()
                        if "lock" not in msg and "busy" not in msg:
                            raise
                        time.sleep(0.2 * (attempt + 1))
                else:
                    logger.info(
                        "[Cache] WAL switch deferred (database locked at "
                        "init); continuing in journal mode %r",
                        mode_row[0],
                    )
        
        return self._conn
    
    def save_identity_identifiers(
        self, 
        resolver_name: str, 
        signature: str, 
        identifiers: list[str]
    ) -> None:
        """Save exact-match identifiers to cache.
        
        Args:
            resolver_name: Name of the resolver that found the identifiers.
            signature: Signature for which identifiers were found.
            identifiers: List of identifier strings to save.
        """
        with self._lock:
            conn = self._get_connection()
            if conn is None:
                return
            identifiers_already_cached: set[str] = set(
                self.fetch_identity_identifiers(resolver_name, signature)
            )
            for ident in identifiers:
                if ident in identifiers_already_cached:
                    continue
                conn.execute(
                    "INSERT INTO CACHE_IDENTITY VALUES (?, ?, ?)",
                    (resolver_name, _signature_key(signature), ident),
                )
            conn.commit()

    def fetch_identity_identifiers(
        self, 
        resolver_name: str, 
        signature: str
    ) -> list[str]:
        """Fetch exact-match identifiers from cache.
        
        Args:
            resolver_name: Name of the resolver.
            signature: Signature to look up.
            
        Returns:
            List of cached identifier strings.
        """
        with self._lock:
            conn = self._get_connection()
            if conn is None:
                return []
            query = ("SELECT IDENTIFIER FROM CACHE_IDENTITY "
                     "WHERE RESOLVER_NAME=? AND SIGNATURE=?")
            key = _signature_key(signature)
            records = conn.execute(query, (resolver_name, key)).fetchall()
            if not records and key != signature:  # pre-S3 full-text rows
                records = conn.execute(
                    query, (resolver_name, signature)).fetchall()
            return [record[0] for record in records]

    def save_similarity_identifiers(
        self, 
        resolver_name: str, 
        signature: str, 
        identifiers: list[tuple[str, float]]
    ) -> None:
        """Save similarity-based identifiers to cache.
        
        Args:
            resolver_name: Name of the resolver that found the identifiers.
            signature: Signature for which identifiers were found.
            identifiers: List of (identifier, similarity) tuples to save.
        """
        with self._lock:
            conn = self._get_connection()
            if conn is None:
                return
            identifiers_already_cached: set[str] = set(
                _ident
                for _ident, _ in self.fetch_similarity_identifiers(
                    resolver_name, signature
                )
            )
            for _ident, _similarity in identifiers:
                if _ident in identifiers_already_cached:
                    continue
                conn.execute(
                    "INSERT INTO CACHE_SIMILARITY VALUES (?, ?, ?, ?)",
                    (resolver_name, _signature_key(signature), _ident,
                     _similarity),
                )
            conn.commit()

    def fetch_similarity_identifiers(
        self, 
        resolver_name: str, 
        signature: str
    ) -> list[tuple[str, float]]:
        """Fetch similarity-based identifiers from cache.
        
        Args:
            resolver_name: Name of the resolver.
            signature: Signature to look up.
            
        Returns:
            List of (identifier, similarity) tuples.
        """
        with self._lock:
            conn = self._get_connection()
            if conn is None:
                return []
            query = ("SELECT IDENTIFIER, SIMILARITY FROM CACHE_SIMILARITY "
                     "WHERE RESOLVER_NAME=? AND SIGNATURE=?")
            key = _signature_key(signature)
            records = conn.execute(query, (resolver_name, key)).fetchall()
            if not records and key != signature:  # pre-S3 full-text rows
                records = conn.execute(
                    query, (resolver_name, signature)).fetchall()
            return records
