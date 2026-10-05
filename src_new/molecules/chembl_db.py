"""Read-only access to a built local ChEMBL mirror DB (OQ-11).

Mirrors the PubChemDB idiom (lazy, immutable, read-only connect; thread-safe
via lock; exists() for auto-degrade wiring). The DB is derived from the EBI
ChEMBL sqlite dump; v1 carries exactly one lookup surface:

    formula -> [CHEMBL_ID]  (exact full_molformula match, ascending numeric)

Schema (built by the OQ-11 builder script):

    CREATE TABLE chembl_compounds (
        chembl_id TEXT PRIMARY KEY,     -- e.g. 'CHEMBL113'
        formula   TEXT NOT NULL         -- ChEMBL full_molformula (Hill order)
    );
    CREATE INDEX idx_formula ON chembl_compounds(formula);
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class ChEMBLDB:
    """Read-only ChEMBL mirror access.

    Usage::

        db = ChEMBLDB("/app/databases/chembl/current/chembl.sqlite")
        db.by_formula("C8H10N4O2", limit=200)  # -> ['CHEMBL113', ...]
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            uri = f"file:{self._db_path}?mode=ro&immutable=1"
            self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        return self._conn

    def _query(self, sql: str, args: tuple) -> list[tuple]:
        with self._lock:
            return self._get_conn().execute(sql, args).fetchall()

    def exists(self) -> bool:
        """True when the DB file is present (auto-degrade wiring hook)."""
        return self._db_path.is_file()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def by_formula(self, formula: str, limit: int = 200) -> list[str]:
        """Formula -> CHEMBL IDs (exact match, ascending numeric order).

        Matches the legacy REST lookup contract (deduped list, capped).
        """
        formula = (formula or "").strip()
        if not formula:
            return []
        rows = self._query(
            "SELECT chembl_id FROM chembl_compounds WHERE formula = ? "
            "ORDER BY CAST(SUBSTR(chembl_id, 7) AS INTEGER) LIMIT ?",
            (formula, int(limit)),
        )
        return [r[0] for r in rows]
