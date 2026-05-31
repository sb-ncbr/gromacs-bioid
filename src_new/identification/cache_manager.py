"""Thread-safe SQLite cache for identifier resolution."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading

from ..config.loader import RunConfig

logger = logging.getLogger("identifier")


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
            """CREATE TABLE "CACHE_IDENTITY" (
                        "RESOLVER_NAME"	TEXT NOT NULL,
                        "SIGNATURE"	    TEXT NOT NULL,
                        "IDENTIFIER"	TEXT NOT NULL,
                        PRIMARY KEY("IDENTIFIER","SIGNATURE","RESOLVER_NAME"));
                    """
        )

        conn.execute(
            """CREATE TABLE "CACHE_SIMILARITY" (
                        "RESOLVER_NAME"	TEXT NOT NULL,
                        "SIGNATURE"	    TEXT NOT NULL,
                        "IDENTIFIER"	TEXT NOT NULL,
                        "SIMILARITY"	REAL,
                        PRIMARY KEY("IDENTIFIER","SIGNATURE","RESOLVER_NAME"));
                    """
        )

        conn.commit()


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
    
    @property
    def _connection(self) -> sqlite3.Connection:
        """Lazy connection initialization."""
        if self._conn is None:
            cache_directory: str = self._config.identifiers_cache.directory
            cache_file: str = self._config.identifiers_cache.file
            self._cache_path = os.path.join(cache_directory, cache_file)
            
            create_empty_cache_if_not_exists(self._cache_path)
            self._conn = sqlite3.connect(self._cache_path, timeout=30.0)
            # Enable WAL mode for better concurrent access
            self._conn.execute("PRAGMA journal_mode=WAL")
        
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
            conn = self._connection
            identifiers_already_cached: set[str] = set(
                self.fetch_identity_identifiers(resolver_name, signature)
            )
            for ident in identifiers:
                if ident in identifiers_already_cached:
                    continue
                conn.execute(
                    "INSERT INTO CACHE_IDENTITY VALUES (?, ?, ?)",
                    (resolver_name, signature, ident),
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
            conn = self._connection
            records = conn.execute(
                "SELECT IDENTIFIER FROM CACHE_IDENTITY WHERE RESOLVER_NAME=? AND SIGNATURE=?",
                (resolver_name, signature),
            ).fetchall()
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
            conn = self._connection
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
                    (resolver_name, signature, _ident, _similarity),
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
            conn = self._connection
            records = conn.execute(
                "SELECT IDENTIFIER, SIMILARITY FROM CACHE_SIMILARITY "
                "WHERE RESOLVER_NAME=? AND SIGNATURE=?",
                (resolver_name, signature),
            ).fetchall()
            return records
