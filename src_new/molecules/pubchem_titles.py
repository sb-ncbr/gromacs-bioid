"""PubChem compound titles (common names) beside the local mirror.

UI pass 2026-11-07: chemical hits were named by their IUPAC name ("[[(2R,3S,
4R,5R)-5-(6-aminopurin-9-yl)-3,4-dihydroxyoxolan-2-yl]methoxy-hydroxy-
phosphoryl] phosphono hydrogen phosphate" for ATP). PubChem's Title is the
compound's common name ("Adenosine-5'-triphosphate", "Cholesterol").

Kept as a SEPARATE SQLite file next to pubchem.sqlite — the mirror itself is
never rewritten or locked, and the file is optional: when it is absent, a
CID has no title, or the title is a bare registry code, every lookup returns
None and callers keep their previous name.

Build (one pass over PubChem Compound/Extras/CID-Title.gz, "cid<TAB>title"):
  python3 -m src_new.molecules.pubchem_titles build CID-Title.gz OUT.sqlite
writes OUT.sqlite.tmp and renames it into place only when complete.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sqlite3
import sys
import time
from functools import lru_cache
from typing import Optional

_DEFAULT = "/app/databases/pubchem/current/pubchem_titles.sqlite"

# Titles that are a vendor/registry code, not a name: fall back to the IUPAC
# name instead (e.g. "SCHEMBL1234567", "AKOS015912345", "CHEMBL25",
# "ZINC000001234567", "MFCD00012345", "DTXSID0021234", "NSC 12345").
_CODE_TITLE = re.compile(
    r"^(SCHEMBL|AKOS|CHEMBL|ZINC|MFCD|DTXSID|DTXCID|NSC|CID|SID|EINECS|CAS|"
    r"UNII|HMS|MLS|SMR|BRD|CCG|STK|STL|BDBM|AC1|Q)[-_ ]?[0-9][0-9A-Z-]*$",
    re.IGNORECASE)


def is_useful_title(title: Optional[str]) -> bool:
    """A title worth showing instead of the IUPAC name."""
    if not title:
        return False
    t = title.strip()
    return bool(t) and len(t) <= 200 and not _CODE_TITLE.match(t)


class PubChemTitles:
    """Read-only CID -> title lookups; every miss is None, never an error."""

    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("PUBCHEM_TITLES_DB", _DEFAULT)
        self._conn = None
        self._tried = False

    def _db(self):
        if not self._tried:
            self._tried = True
            try:
                if os.path.exists(self.path):
                    self._conn = sqlite3.connect(
                        f"file:{self.path}?mode=ro&immutable=1", uri=True,
                        check_same_thread=False)
            except Exception:
                self._conn = None
        return self._conn

    def title(self, cid) -> Optional[str]:
        db = self._db()
        if db is None:
            return None
        try:
            row = db.execute("SELECT title FROM titles WHERE cid = ?", (int(cid),)).fetchone()
        except Exception:
            return None
        t = row[0] if row else None
        return t.strip() if is_useful_title(t) else None


@lru_cache(maxsize=1)
def default_titles() -> PubChemTitles:
    return PubChemTitles()


def build(gz_path: str, out_path: str, batch: int = 200_000) -> dict:
    """Stream CID-Title.gz into OUT.sqlite (atomic rename on success)."""
    tmp = out_path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    t0 = time.time()
    con = sqlite3.connect(tmp)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("CREATE TABLE titles (cid INTEGER PRIMARY KEY, title TEXT NOT NULL)")
    rows, n, bad = [], 0, 0
    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            cid, sep, title = line.rstrip("\n").partition("\t")
            if not sep or not cid.isdigit() or not title:
                bad += 1
                continue
            rows.append((int(cid), title))
            if len(rows) >= batch:
                con.executemany("INSERT OR REPLACE INTO titles VALUES (?, ?)", rows)
                n += len(rows)
                rows.clear()
    if rows:
        con.executemany("INSERT OR REPLACE INTO titles VALUES (?, ?)", rows)
        n += len(rows)
    con.commit()
    con.close()
    os.replace(tmp, out_path)
    meta = {"source": os.path.basename(gz_path), "rows": n, "skipped_lines": bad,
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": round(time.time() - t0, 1)}
    with open(out_path + ".json", "w") as fh:
        json.dump(meta, fh, indent=1)
    return meta


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "build":
        print(json.dumps(build(sys.argv[2], sys.argv[3])))
    else:
        sys.exit("usage: python3 -m src_new.molecules.pubchem_titles build CID-Title.gz OUT.sqlite")
