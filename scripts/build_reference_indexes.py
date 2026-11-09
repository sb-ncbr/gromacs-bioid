#!/usr/bin/env python3
"""Build the local SQLite indexes for the supplementary resolvers.

    build_reference_indexes.py sifts       pdb_chain_uniprot.tsv.gz         OUT.sqlite
    build_reference_indexes.py swisslipids lipids.tsv.gz                    OUT.sqlite
    build_reference_indexes.py chebi       compounds.tsv.gz structures.tsv.gz OUT.sqlite

Each index is written to OUT.sqlite.tmp and renamed into place only after it
is complete and non-empty, so a failed build never leaves a partial index for
a resolver to read. Schemas are read by src_new/identification/reference_indexes.py.
"""
from __future__ import annotations

import csv
import gzip
import os
import sqlite3
import sys
from datetime import datetime, timezone

csv.field_size_limit(sys.maxsize)


def _open(path: str):
    # SwissLipids carries a few non-UTF-8 bytes in names; structures and
    # keys are ASCII, so replacing undecodable bytes loses nothing we use.
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="")
    return open(path, encoding="utf-8", errors="replace", newline="")


def _ik_parts(key: str) -> tuple[str, str, str] | None:
    """(full, first two blocks, first block) of a standard InChIKey."""
    key = (key or "").strip()
    if key.startswith("InChIKey="):
        key = key[len("InChIKey="):]
    if len(key) != 27 or key.count("-") != 2:
        return None
    return key, key[:25], key[:14]


def _finish(con: sqlite3.Connection, tmp: str, out: str, table: str, source: str) -> int:
    n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("source", source), ("rows", str(n)),
        ("built_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))])
    con.commit()
    con.execute("VACUUM")
    con.close()
    if n == 0:
        os.unlink(tmp)
        raise SystemExit(f"{table}: no rows parsed from {source}; index not written")
    os.replace(tmp, out)
    return n


def _new_db(out: str) -> tuple[sqlite3.Connection, str]:
    tmp = out + ".tmp"
    if os.path.exists(tmp):
        os.unlink(tmp)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    return sqlite3.connect(tmp), tmp


def build_sifts(src: str, out: str) -> int:
    con, tmp = _new_db(out)
    con.execute("CREATE TABLE chain_uniprot (pdb TEXT, chain TEXT, uniprot TEXT, "
                "PRIMARY KEY (pdb, chain, uniprot)) WITHOUT ROWID")
    rows = set()
    with _open(src) as f:
        for line in f:
            if line.startswith("#") or line.startswith("PDB\t"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3 or not parts[2]:
                continue
            rows.add((parts[0].upper(), parts[1], parts[2].upper()))
    con.executemany("INSERT INTO chain_uniprot VALUES (?, ?, ?)", sorted(rows))
    return _finish(con, tmp, out, "chain_uniprot", os.path.basename(src))


def build_swisslipids(src: str, out: str) -> int:
    con, tmp = _new_db(out)
    con.execute("CREATE TABLE lipids (slm_id TEXT PRIMARY KEY, level TEXT, name TEXT, "
                "smiles TEXT, inchikey TEXT, ik25 TEXT, ik14 TEXT, chebi TEXT, lipidmaps TEXT)")
    con.execute("CREATE TABLE abbrevs (abbrev TEXT, slm_id TEXT)")
    with _open(src) as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader)
        col = {name.strip(): i for i, name in enumerate(header)}
        i_id, i_level, i_name = col["Lipid ID"], col["Level"], col["Name"]
        i_abbr, i_smiles = col["Abbreviation*"], col["SMILES (pH7.3)"]
        i_ik, i_chebi, i_lm = col["InChI key (pH7.3)"], col["CHEBI"], col["LIPID MAPS"]
        lipids, abbrevs = [], []
        for row in reader:
            if len(row) <= i_lm:
                continue
            ik = _ik_parts(row[i_ik])
            lipids.append((row[i_id], row[i_level], row[i_name], row[i_smiles] or None,
                           ik[0] if ik else None, ik[1] if ik else None, ik[2] if ik else None,
                           row[i_chebi] or None, row[i_lm] or None))
            for a in row[i_abbr].split("|"):
                if a.strip():
                    abbrevs.append((a.strip(), row[i_id]))
    con.executemany("INSERT INTO lipids VALUES (?,?,?,?,?,?,?,?,?)", lipids)
    con.executemany("INSERT INTO abbrevs VALUES (?, ?)", abbrevs)
    for idx in ("lipids(ik25)", "lipids(ik14)", "abbrevs(abbrev)"):
        con.execute(f"CREATE INDEX ix_{idx.replace('(', '_').rstrip(')')} ON {idx}")
    return _finish(con, tmp, out, "lipids", os.path.basename(src))


def build_chebi(compounds: str, structures: str, out: str) -> int:
    con, tmp = _new_db(out)
    con.execute("CREATE TABLE compounds (chebi_id TEXT PRIMARY KEY, name TEXT, stars INTEGER, "
                "smiles TEXT, inchikey TEXT, ik25 TEXT, ik14 TEXT)")
    meta: dict[str, tuple[str, int]] = {}
    with _open(compounds) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            acc = (row.get("chebi_accession") or "").strip()
            if not acc.startswith("CHEBI:"):
                continue
            try:
                stars = int(row.get("stars") or 0)
            except ValueError:
                stars = 0
            meta[row["id"]] = (acc, (row.get("ascii_name") or row.get("name") or "").strip(), stars)
    seen: set[str] = set()
    rows = []
    with _open(structures) as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if str(row.get("default_structure", "")).strip().lower() not in ("t", "true", "1"):
                continue
            m = meta.get(row.get("compound_id", ""))
            ik = _ik_parts(row.get("standard_inchi_key", ""))
            if not m or not ik or m[0] in seen:
                continue
            seen.add(m[0])
            rows.append((m[0], m[1], m[2], (row.get("smiles") or "").strip() or None,
                         ik[0], ik[1], ik[2]))
    con.executemany("INSERT INTO compounds VALUES (?,?,?,?,?,?,?)", rows)
    con.execute("CREATE INDEX ix_compounds_ik25 ON compounds(ik25)")
    con.execute("CREATE INDEX ix_compounds_ik14 ON compounds(ik14)")
    return _finish(con, tmp, out, "compounds", os.path.basename(structures))


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        raise SystemExit(__doc__)
    kind, args = argv[1], argv[2:]
    if kind == "sifts" and len(args) == 2:
        n = build_sifts(*args)
    elif kind == "swisslipids" and len(args) == 2:
        n = build_swisslipids(*args)
    elif kind == "chebi" and len(args) == 3:
        n = build_chebi(*args)
    else:
        raise SystemExit(__doc__)
    print(f"{kind}: {n} rows -> {args[-1]}")


if __name__ == "__main__":
    main(sys.argv)
