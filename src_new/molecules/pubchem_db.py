"""Local PubChem lookup database: build and read the mirror SQLite.

Replaces the PUG-REST calls we can serve locally (see
``docs/PLAN_PUBCHEM_MIRROR.md`` §8 contract map):

* ``formula -> [CID]``      (identify: formula + hfamily resolvers)
* ``CID -> SMILES``         (verification fetch path)
* ``InChIKey -> CID/SMILES``(identity checks + verification fetch path)

Data sources: PubChem ``Compound/Extras/CID-SMILES.gz`` (``CID\tSMILES``) and
``CID-InChI-Key.gz`` (``CID\tInChI\tInChIKey``), both CID-ascending. Molecular
formula and exact mass are derived from SMILES with RDKit at build time
(``CalcMolFormula`` emits Hill-ordered formulas, matching PubChem's own
convention).

The builder streams both archives in ascending-CID order and writes SQLite in
batches; a checkpoint file records the last fully-written CID so a killed pod
can resume (``build(..., resume=True)``).
"""

from __future__ import annotations

import gzip
import json
import logging
import multiprocessing as mp
import os
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Iterator, NamedTuple

logger = logging.getLogger(__name__)

_BATCH_ROWS = 100_000
_CHECKPOINT_ROWS = 5_000_000
_INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
_FORMULA_PART_RE = re.compile(r"([A-Z][a-z]?)(\d*)")
# Trailing formal-charge annotation emitted by RDKit CalcMolFormula
# ('C2H3O2-', 'C7H8N4O2+2', 'C20H24O2-2'). PUG formula search is
# charge-insensitive, so the index key strips it.
_CHARGE_SUFFIX_RE = re.compile(r"[+-]+\d*$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS compounds (
    cid          INTEGER PRIMARY KEY,
    smiles       TEXT NOT NULL,
    inchikey     TEXT,
    formula_hill TEXT NOT NULL,
    exact_mass   REAL,
    iupac_name   TEXT,
    has_synonyms INTEGER NOT NULL DEFAULT 0
);
"""


class CompoundRow(NamedTuple):
    """One row of the mirror DB."""

    cid: int
    smiles: str
    inchikey: str | None
    formula_hill: str
    exact_mass: float | None
    # Item-4 correction (user ruling 11-03): annotation pre-fill columns.
    # The only signals live fetch adds over the mirror are iupac_name and
    # synonyms; supplying them locally removes the NCBI-throttle exposure
    # for mirror-hit rows entirely. Absent (None/False) on legacy mirrors
    # built before the extension — the scorer live-fills those as before.
    iupac_name: str | None = None
    has_synonyms: bool = False


def normalize_formula(formula: str) -> str:
    """Reorder a molecular formula to Hill order (C, H, then alphabetical).

    Accepts loose inputs like ``'H6O2C2'`` or ``'OHCH3'``-style repetition and
    emits the canonical Hill string (``'C2H6O'``). Raises ValueError on input
    that is not element/count pairs.
    """
    formula = formula.strip()
    if not formula:
        raise ValueError("empty formula")
    parts: dict[str, int] = {}
    pos = 0
    for match in _FORMULA_PART_RE.finditer(formula):
        if match.start() != pos:
            raise ValueError(f"unparseable formula: {formula!r}")
        pos = match.end()
        parts[match.group(1)] = parts.get(match.group(1), 0) + int(match.group(2) or "1")
    if pos != len(formula):
        raise ValueError(f"unparseable formula: {formula!r}")

    def emit(element: str) -> str:
        count = parts.pop(element, 0)
        if count == 0:
            return ""
        return element + (str(count) if count > 1 else "")

    out = emit("C") + emit("H")
    out += "".join(el + (str(parts[el]) if parts[el] > 1 else "") for el in sorted(parts))
    return out


def _derive_chemistry(batch: list[tuple[int, str]]) -> list[tuple[int, str, str, float | None, bool]]:
    """Worker: (cid, smiles) -> (cid, smiles, formula_hill, exact_mass, parsed)."""
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    out: list[tuple[int, str, str, float | None, bool]] = []
    for cid, smiles in batch:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            out.append((cid, smiles, "", None, False))
            continue
        # Formula convention (parity-verified 2026-09-24): PUG fastformula is
        # insensitive to BOTH isotopes and formal charge/protonation state
        # (zwitterion CID 136728936 'C5H5N5O-2' and dianion CID 19752125
        # 'C20H24O2-2' answer the PLAIN formula queries 'C5H5N5O'/'C20H24O2').
        # CalcMolFormula merges isotopes by default (rdkit 2026.03) and
        # appends charge as a trailing '±n' annotation - strip it so the
        # index key matches the PUG query form. Original SMILES preserved.
        for atom in mol.GetAtoms():
            atom.SetIsotope(0)
        formula = rdMolDescriptors.CalcMolFormula(mol)
        formula = _CHARGE_SUFFIX_RE.sub("", formula)
        out.append(
            (
                cid,
                smiles,
                formula,
                float(rdMolDescriptors.CalcExactMolWt(mol)),
                True,
            )
        )
    return out


def _iter_smiles(path: Path, after_cid: int = 0) -> Iterator[tuple[int, str]]:
    """Yield (cid, smiles) from CID-SMILES.gz, skipping cids <= after_cid."""
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            cid = int(parts[0])
            if cid > after_cid:
                yield cid, parts[1]


def _iter_inchikeys(path: Path, after_cid: int = 0) -> Iterator[tuple[int, str]]:
    """Yield (cid, inchikey) from CID-InChI-Key.gz (3-col: CID, InChI, InChIKey).

    CID-ascending like the SMILES file, so the builder can zip-merge both
    streams in O(1) memory instead of holding ~120M keys in a dict.
    """
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2 or not parts[0].isdigit():
                continue
            ik = parts[-1]
            if not _INCHIKEY_RE.match(ik):
                continue
            cid = int(parts[0])
            if cid > after_cid:
                yield cid, ik


def _iter_iupac(path: Path, after_cid: int = 0) -> Iterator[tuple[int, str]]:
    """Yield (cid, iupac_name) from CID-IUPAC.gz (2-col, CID-ascending).

    Item-4 correction (user ruling 11-03): the mirror structurally lacks
    IUPAC names and synonyms — the only signals live fetch adds. Extending
    the mirror from the Extras bulk files supplies them locally and
    removes the NCBI-throttle exposure for mirror-hit rows entirely.
    """
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            cid = int(parts[0])
            if cid > after_cid:
                yield cid, parts[1].strip()


def _iter_synonyms(path: Path, after_cid: int = 0) -> Iterator[tuple[int, bool]]:
    """Yield (cid, has_synonym_row) from CID-Synonym-filtered.gz.

    Format: one synonym per line (2-col, CID-ascending with MULTIPLE rows
    per CID). The mirror stores only a has_synonyms FLAG (not the synonym
    list) — the annotation scorer's 'synonyms' signal is presence-only,
    and storing ~1.5B synonym strings would triple the DB. Rows with a
    blank synonym column still prove the CID participated in the
    synonym file and count as has_synonyms (defensive; the filtered file
    has no blank rows in practice).
    """
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) != 2 or not parts[0].isdigit():
                continue
            cid = int(parts[0])
            if cid > after_cid:
                yield cid, True


def _checkpoint_path(db_path: Path) -> Path:
    return db_path.with_suffix(".checkpoint.json")


def _read_checkpoint(db_path: Path) -> dict:
    try:
        return json.loads(_checkpoint_path(db_path).read_text())
    except (OSError, json.JSONDecodeError):
        return {"done_upto_cid": 0, "rows_written": 0}


def _write_checkpoint(db_path: Path, done_upto_cid: int, rows_written: int) -> None:
    _checkpoint_path(db_path).write_text(
        json.dumps({"done_upto_cid": done_upto_cid, "rows_written": rows_written})
    )


def build(
    db_path: str | Path,
    smiles_gz: str | Path,
    inchikey_gz: str | Path,
    iupac_gz: str | Path | None = None,
    synonyms_gz: str | Path | None = None,
    limit: int | None = None,
    resume: bool = True,
    workers: int | None = None,
) -> dict:
    """Build (or resume) the mirror DB.

    Args:
        db_path: Target SQLite file (inside a staging dir).
        smiles_gz: ``CID-SMILES.gz`` path.
        inchikey_gz: ``CID-InChI-Key.gz`` path.
        iupac_gz: ``CID-IUPAC.gz`` path (item-4 correction 11-03: annotation
            pre-fill — the mirror gains an ``iupac_name`` column). Optional;
            a build without it produces the legacy 5-column schema.
        synonyms_gz: ``CID-Synonym-filtered.gz`` path (annotation pre-fill —
            the mirror gains a ``has_synonyms`` flag). Optional, same rule.
        limit: If set, only the first ``limit`` CIDs are imported (sample builds).
        resume: Continue from the checkpoint file when present.
        workers: RDKit derivation processes (default: min(8, cpu_count)).

    Returns:
        Stats dict (also persisted into build_metadata by the caller).
    """
    db_path = Path(db_path)
    smiles_gz = Path(smiles_gz)
    inchikey_gz = Path(inchikey_gz)
    iupac_gz = Path(iupac_gz) if iupac_gz else None
    synonyms_gz = Path(synonyms_gz) if synonyms_gz else None
    with_annotations = iupac_gz is not None or synonyms_gz is not None
    started = time.time()
    workers = workers or min(8, mp.cpu_count() or 1)

    # RDKit emits per-molecule warnings ('not removing hydrogen atom ...') at
    # a rate that floods job logs on a 120M-row build; parse failures are
    # still counted and sampled via stats. Silence globally (fork-inherited).
    try:
        from rdkit import RDLogger

        RDLogger.DisableLog("rdApp.*")
    except Exception:  # pragma: no cover - rdkit always present in build image
        pass

    fresh = not db_path.exists()
    state = _read_checkpoint(db_path) if (resume and db_path.exists()) else {"done_upto_cid": 0, "rows_written": 0}
    done_upto = int(state.get("done_upto_cid", 0))
    rows_written = int(state.get("rows_written", 0))
    if done_upto:
        logger.info("pubchem_db.build resuming after cid=%d (rows=%d)", done_upto, rows_written)

    # Zip-merge both CID-ascending streams (O(1) memory): advance the
    # InChIKey iterator until it catches up with the current SMILES cid.
    ik_iter = _iter_inchikeys(inchikey_gz, after_cid=done_upto if resume else 0)
    ik_cid: int | None = None
    ik_val: str | None = None

    def _advance_ik() -> None:
        nonlocal ik_cid, ik_val
        try:
            ik_cid, ik_val = next(ik_iter)
        except StopIteration:
            ik_cid, ik_val = None, None

    _advance_ik()

    def _ik_for(cid: int) -> str | None:
        nonlocal ik_cid, ik_val
        while ik_cid is not None and ik_cid < cid:
            _advance_ik()
        return ik_val if ik_cid == cid else None

    # Item-4 correction (11-03): same zip-merge for the annotation
    # pre-fill streams (CID-ascending Extras files).
    iup_iter = (_iter_iupac(iupac_gz, after_cid=done_upto if resume else 0)
                if iupac_gz else None)
    iup_cid: int | None = None
    iup_val: str | None = None

    def _advance_iup() -> None:
        nonlocal iup_cid, iup_val
        try:
            iup_cid, iup_val = next(iup_iter)
        except StopIteration:
            iup_cid, iup_val = None, None

    if iup_iter is not None:
        _advance_iup()

    def _iup_for(cid: int) -> str | None:
        nonlocal iup_cid, iup_val
        while iup_cid is not None and iup_cid < cid:
            _advance_iup()
        return iup_val if iup_cid == cid else None

    syn_iter = (_iter_synonyms(synonyms_gz, after_cid=done_upto if resume else 0)
                if synonyms_gz else None)
    syn_cid: int | None = None

    def _advance_syn() -> None:
        nonlocal syn_cid
        try:
            syn_cid, _flag = next(syn_iter)
        except StopIteration:
            syn_cid = None

    if syn_iter is not None:
        _advance_syn()

    def _has_syn_for(cid: int) -> bool:
        nonlocal syn_cid
        while syn_cid is not None and syn_cid < cid:
            _advance_syn()
        return syn_cid == cid

    # Explicit column lists: the extended schema has two more columns with
    # defaults, so a legacy-shaped insert (no annotation data) fills them
    # with NULL/0 instead of erroring on the column count.
    insert_sql = (
        "INSERT OR REPLACE INTO compounds "
        "(cid, smiles, inchikey, formula_hill, exact_mass"
        + (", iupac_name, has_synonyms" if with_annotations else "")
        + ") VALUES (?,?,?,?,?" + (",?,?" if with_annotations else "") + ")")

    conn = sqlite3.connect(db_path)
    if fresh:
        conn.executescript(SCHEMA)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA page_size=32768")

    parse_failures = 0
    ik_matched = [0]
    iup_matched = [0]
    syn_flagged = [0]
    total_in = 0
    batch_cids: list[int] = []
    batch_smiles: list[str] = []
    last_checkpoint_rows = rows_written

    def flush(pending_batches):
        nonlocal parse_failures, rows_written, done_upto, last_checkpoint_rows
        rows: list[tuple] = []
        for derived in pending_batches:
            for cid, smi, formula, mass, parsed in derived:
                parse_failures += 0 if parsed else 1
                ik = _ik_for(cid)
                ik_matched[0] += 1 if ik else 0
                row = (cid, smi, ik, formula, mass)
                if with_annotations:
                    iup = _iup_for(cid)
                    iup_matched[0] += 1 if iup else 0
                    has_syn = _has_syn_for(cid)
                    syn_flagged[0] += 1 if has_syn else 0
                    row = row + (iup, 1 if has_syn else 0)
                rows.append(row)
        conn.executemany(insert_sql, rows)
        conn.commit()
        rows_written += len(rows)
        done_upto = rows[-1][0]
        if rows_written - last_checkpoint_rows >= _CHECKPOINT_ROWS:
            _write_checkpoint(db_path, done_upto, rows_written)
            last_checkpoint_rows = rows_written
            logger.info("pubchem_db.build checkpoint: cid=%d rows=%d", done_upto, rows_written)

    ctx = mp.get_context("fork") if os.name == "posix" else mp.get_context()
    pending: list = []
    pool = ctx.Pool(workers) if workers > 1 else None

    def submit(b_cids, b_smiles):
        payload = list(zip(b_cids, b_smiles))
        if pool is not None:
            pending.append(pool.apply_async(_derive_chemistry, (payload,)))
        else:
            pending.append(_derive_chemistry(payload))
        # keep at most 2*workers batches in flight; flush the oldest when full
        if len(pending) >= 2 * workers:
            _flush_oldest()

    def _flush_oldest():
        oldest = pending.pop(0)
        derived = oldest.get() if hasattr(oldest, "get") else oldest
        flush([derived])

    for cid, smiles in _iter_smiles(smiles_gz, after_cid=done_upto if resume else 0):
        total_in += 1
        batch_cids.append(cid)
        batch_smiles.append(smiles)
        if len(batch_cids) >= (_BATCH_ROWS // max(1, workers // 2)):
            submit(batch_cids, batch_smiles)
            batch_cids, batch_smiles = [], []
        if limit is not None and total_in >= limit:
            break
    if batch_cids:
        submit(batch_cids, batch_smiles)
    while pending:
        _flush_oldest()
    if pool is not None:
        pool.close()
        pool.join()

    logger.info("Building indexes ...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_formula ON compounds(formula_hill)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_inchikey ON compounds(inchikey)")
    conn.execute("ANALYZE")
    conn.execute("PRAGMA optimize")
    conn.commit()
    conn.close()

    _write_checkpoint(db_path, done_upto, rows_written)
    stats = {
        "rows_streamed": total_in,
        "rows_written": rows_written,
        "smiles_parse_failures": parse_failures,
        "inchikey_matched": ik_matched[0],
        "iupac_matched": iup_matched[0] if with_annotations else None,
        "synonyms_flagged": syn_flagged[0] if with_annotations else None,
        "limit": limit,
        "done_upto_cid": done_upto,
        "elapsed_s": round(time.time() - started, 1),
    }
    logger.info("pubchem_db.build finished: %s", stats)
    return stats


class PubChemDB:
    """Read-only access to a built mirror DB.

    One instance per process (lazy connect, never shared across forks).
    Opened immutable + read-only: safe on NFS and for concurrent readers.

    Usage::

        db = PubChemDB("/app/databases/pubchem/current/pubchem.sqlite")
        db.by_cid(702)                  # -> CompoundRow | None
        db.by_inchikey("LFQSC...")      # -> CompoundRow | None
        db.by_formula("C2H6O", limit=10)  # -> list[int] (ascending cid)
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        # Item-4 correction (11-03): annotation pre-fill columns
        # (iupac_name, has_synonyms) — resolved lazily because the DB may
        # not exist yet at construction; legacy mirrors degrade to NULL/0.
        self._ann_select: str | None = None
        # One shared read-only connection per instance; a lock serializes
        # queries so a single instance is safe across `threads` celery pools
        # (sqlite rejects cross-thread cursors otherwise). Queries are
        # sub-millisecond, so contention is invisible. check_same_thread=False
        # is safe precisely because the lock exists.
        self._lock = threading.Lock()

    def _sel(self) -> str:
        """SELECT suffix for the annotation pre-fill columns. Legacy mirrors
        (built before the 11-03 extension) lack the columns and degrade to
        NULL/0 — readers then live-fill as before."""
        if self._ann_select is None:
            try:
                cols = {r[1] for r in self._query(
                    "PRAGMA table_info(compounds)", ())}
                self._ann_select = (
                    ", iupac_name, has_synonyms"
                    if {"iupac_name", "has_synonyms"} <= cols
                    else ", NULL AS iupac_name, 0 AS has_synonyms")
            except sqlite3.Error:
                return ""  # DB not openable yet: legacy column set
        return self._ann_select

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            uri = f"file:{self._db_path}?mode=ro&immutable=1"
            self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        return self._conn

    def _query(self, sql: str, args: tuple) -> list[tuple]:
        with self._lock:
            return self._get_conn().execute(sql, args).fetchall()

    def exists(self) -> bool:
        """True when the DB file is present (used for auto-degrade wiring)."""
        return self._db_path.is_file()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _to_row(raw: tuple) -> CompoundRow:
        # 5-tuple = legacy mirror (no annotation columns); 7-tuple =
        # extended mirror (item-4 correction 11-03).
        iupac = raw[5] if len(raw) > 5 else None
        has_syn = bool(raw[6]) if len(raw) > 6 else False
        return CompoundRow(cid=raw[0], smiles=raw[1], inchikey=raw[2],
                           formula_hill=raw[3], exact_mass=raw[4],
                           iupac_name=iupac, has_synonyms=has_syn)

    def by_cid(self, cid: int | str) -> CompoundRow | None:
        """Look up a compound by PubChem CID."""
        raw = self._query(
            f"SELECT cid, smiles, inchikey, formula_hill, "
            f"exact_mass{self._sel()} FROM compounds WHERE cid=?",
            (int(cid),),
        )
        return self._to_row(raw[0]) if raw else None

    def by_cids(self, cids, chunk_size: int = 500) -> dict[str, CompoundRow]:
        """Bulk CID lookup via chunked SQL IN (D-10: the verification rerank
        resolves ALL chemical candidates through the mirror, network-free).

        Returns {str(cid): CompoundRow}; unknown/malformed CIDs are absent.
        """
        ids = []
        seen = set()
        for c in cids:
            s = str(c)
            if s.isdigit() and s not in seen:
                seen.add(s)
                ids.append(int(s))
        out: dict[str, CompoundRow] = {}
        for i in range(0, len(ids), chunk_size):
            chunk = ids[i:i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            raw = self._query(
                f"SELECT cid, smiles, inchikey, formula_hill, "
                f"exact_mass{self._sel()} "
                f"FROM compounds WHERE cid IN ({placeholders})",
                tuple(chunk))
            for r in raw:
                row = self._to_row(r)
                out[str(row.cid)] = row
        return out

    def by_inchikey_block(self, inchikey: str) -> CompoundRow | None:
        """InChIKey connectivity-block (first block) lookup, lowest CID wins.

        Finds stereo/protonation variants of the queried compound: the mirror
        keys rows by full InChIKey, so an exact miss for a variant key can
        still resolve the shared connectivity block. Used as an offline
        fallback for structure fetches (skeleton comparisons are
        stereo/H-insensitive by design).
        """
        block = (inchikey or "").strip().upper().split("-")[0]
        if not block:
            return None
        raw = self._query(
            f"SELECT cid, smiles, inchikey, formula_hill, "
            f"exact_mass{self._sel()} FROM compounds "
            "WHERE inchikey >= ? AND inchikey < ? ORDER BY inchikey, cid LIMIT 1",
            (block, block + chr(0x7F)),
        )
        return self._to_row(raw[0]) if raw else None

    def by_inchikey(self, inchikey: str) -> CompoundRow | None:
        """Look up a compound by full InChIKey (lowest-CID row on duplicates)."""
        raw = self._query(
            f"SELECT cid, smiles, inchikey, formula_hill, "
            f"exact_mass{self._sel()} FROM compounds WHERE inchikey=?",
            (inchikey.strip(),),
        )
        return self._to_row(raw[0]) if raw else None

    def by_formula(self, formula: str, limit: int = 10) -> list[int]:
        """Formula -> CIDs (ascending, capped like PUG MaxRecords semantics).

        The formula is normalized to Hill order first, so callers may pass
        loose element orderings.
        """
        hill = normalize_formula(formula)
        if not hill:
            return []
        rows = self._query(
            "SELECT cid FROM compounds WHERE formula_hill=? ORDER BY cid LIMIT ?",
            (hill, int(limit)),
        )
        return [r[0] for r in rows]

    def count(self) -> int:
        """Total row count."""
        return self._query("SELECT COUNT(*) FROM compounds", ())[0][0]

    def __del__(self) -> None:  # pragma: no cover - defensive cleanup
        try:
            self.close()
        except Exception:
            pass
