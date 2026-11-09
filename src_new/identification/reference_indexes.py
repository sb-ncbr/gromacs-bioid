"""Read-only access to the local reference indexes (SIFTS, SwissLipids, ChEBI).

The indexes are SQLite files built by scripts/build_reference_indexes.py on
the shared databases volume. They are opened read-only and immutable (no
locking, which NFS does not do reliably) and cached per process. A missing
or unreadable file reads as "no index": every lookup returns nothing.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading

logger = logging.getLogger("identifier")

_lock = threading.Lock()
_connections: dict[str, sqlite3.Connection | None] = {}


def index_available(path: str) -> bool:
    return bool(path) and os.path.isfile(path)


def _connect(path: str) -> sqlite3.Connection | None:
    with _lock:
        if path in _connections:
            return _connections[path]
        con = None
        if index_available(path):
            try:
                con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True,
                                      check_same_thread=False)
                con.execute("SELECT 1 FROM meta LIMIT 1")
            except sqlite3.Error as exc:
                logger.warning("reference index %s unreadable: %s", path, exc)
                con = None
        _connections[path] = con
        return con


def _query(path: str, sql: str, args: tuple) -> list[tuple]:
    con = _connect(path)
    if con is None:
        return []
    try:
        with _lock:
            return con.execute(sql, args).fetchall()
    except sqlite3.Error as exc:
        logger.warning("reference index %s query failed: %s", path, exc)
        return []


def inchikey_blocks(key: str) -> tuple[str, str, str] | None:
    """(full key, first two blocks, first block) of a standard InChIKey."""
    key = (key or "").strip()
    if key.startswith("InChIKey="):
        key = key[len("InChIKey="):]
    if len(key) != 27 or key.count("-") != 2:
        return None
    return key, key[:25], key[:14]


# -- SIFTS -------------------------------------------------------------------

def sifts_uniprot(path: str, pdb_id: str, chain: str) -> list[str]:
    """UniProt accessions SIFTS maps one PDB chain to (sorted)."""
    rows = _query(path, "SELECT uniprot FROM chain_uniprot WHERE pdb = ? AND chain = ?",
                  (pdb_id.upper(), chain))
    return sorted({r[0] for r in rows})


# -- SwissLipids -------------------------------------------------------------

_LIPID_COLS = "slm_id, level, name, smiles, inchikey"


def swisslipids_by_ik(path: str, block: str, column: str) -> list[tuple]:
    if column not in ("ik25", "ik14"):
        raise ValueError(column)
    return _query(path, f"SELECT {_LIPID_COLS} FROM lipids WHERE {column} = ? AND smiles IS NOT NULL "
                        "ORDER BY slm_id", (block,))


def swisslipids_by_abbrev(path: str, abbrev: str) -> list[tuple]:
    return _query(path, f"SELECT {', '.join('l.' + c.strip() for c in _LIPID_COLS.split(','))} "
                        "FROM abbrevs a JOIN lipids l USING (slm_id) "
                        "WHERE a.abbrev = ? AND l.smiles IS NOT NULL ORDER BY l.slm_id", (abbrev,))


def swisslipids_record(path: str, slm_id: str) -> tuple | None:
    rows = _query(path, f"SELECT {_LIPID_COLS} FROM lipids WHERE slm_id = ?", (slm_id,))
    return rows[0] if rows else None


# -- ChEBI -------------------------------------------------------------------

_CHEBI_COLS = "chebi_id, name, stars, smiles, inchikey"


def chebi_by_ik(path: str, block: str, column: str) -> list[tuple]:
    if column not in ("ik25", "ik14"):
        raise ValueError(column)
    return _query(path, f"SELECT {_CHEBI_COLS} FROM compounds WHERE {column} = ? "
                        "ORDER BY stars DESC, chebi_id", (block,))


def chebi_record(path: str, chebi_id: str) -> tuple | None:
    rows = _query(path, f"SELECT {_CHEBI_COLS} FROM compounds WHERE chebi_id = ?", (chebi_id,))
    return rows[0] if rows else None
