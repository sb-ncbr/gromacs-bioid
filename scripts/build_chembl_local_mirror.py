#!/usr/bin/env python3
"""Build the local ChEMBL formula mirror (OQ-11).

Downloads the EBI ChEMBL sqlite dump, distils the formula -> CHEMBL_ID
mapping into a small read-optimized sqlite on the databases PVC, and
atomically activates it via the `current` symlink (layout identical to
blast/* and pubchem mirrors).

Compound formula source selection (schema sniff):
  1. compound_properties.full_molformula (present in recent ChEMBL dumps)
  2. fallback: derive Hill formula from compound_structures.canonical_smiles
     via RDKit (defensive against upstream schema drift)

Usage (in-pod):
  python3 build_chembl_local_mirror.py --version 37 \
      --root /app/databases/chembl [--keep-raw]

Idempotent: resume-safe download (.part), skips completed steps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

BASE = "https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb"
SELF_CHECK_FORMULA = "C8H10N4O2"  # caffeine -> must contain CHEMBL113


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def download(url: str, dest: Path) -> str:
    """Resume-safe download to dest; returns md5."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    have = tmp.stat().st_size if tmp.exists() else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "ab") as f:
        total = int(r.headers.get("Content-Length") or 0) + have
        log(f"download start {url} resume={have} total={total}")
        n = have
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            n += len(chunk)
            if n and n % (500 << 20) < (1 << 20):
                log(f"  {n} bytes ({n/1e9:.2f} GB) @ {n/(time.time()-t0)/1e6:.1f} MB/s")
    tmp.rename(dest)
    md5 = hashlib.md5(dest.read_bytes()).hexdigest()
    log(f"download done -> {dest} ({dest.stat().st_size} bytes)")
    return md5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--keep-raw", action="store_true")
    args = ap.parse_args()

    v = args.version
    root = Path(args.root)
    ver_dir = root / f"v{v}"
    staging = root / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)

    tgz = staging / f"chembl_{v}_sqlite.tar.gz"
    url = f"{BASE}/latest/chembl_{v}_sqlite.tar.gz"
    if not tgz.exists():
        download(url, tgz)
    else:
        log(f"tarball already present ({tgz.stat().st_size} bytes)")

    extract_dir = staging / f"chembl_{v}"
    big_db = None
    if not extract_dir.exists():
        log("extracting tarball…")
        with tarfile.open(tgz) as tf:
            tf.extractall(staging)
    for cand in extract_dir.rglob("*.db"):
        big_db = cand
        break
    if big_db is None:
        log("ERROR: no .db inside tarball"); return 2
    log(f"source db: {big_db} ({big_db.stat().st_size/1e9:.2f} GB)")

    # schema sniff
    conn = sqlite3.connect(f"file:{big_db}?mode=ro", uri=True)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(compound_properties)")}
    have_formula_col = "full_molformula" in cols
    log(f"compound_properties.full_molformula present: {have_formula_col}")

    ver_dir.mkdir(parents=True, exist_ok=True)
    out_db = ver_dir / "chembl.sqlite"
    tmp_db = out_db.with_suffix(".building")
    if tmp_db.exists():
        tmp_db.unlink()
    out = sqlite3.connect(tmp_db)
    out.execute("PRAGMA journal_mode=OFF")
    out.execute("PRAGMA synchronous=OFF")
    out.execute("CREATE TABLE chembl_compounds (chembl_id TEXT PRIMARY KEY, formula TEXT NOT NULL)")

    t0 = time.time()
    if have_formula_col:
        sql = """
            SELECT m.chembl_id, p.full_molformula
            FROM molecule_dictionary m
            JOIN compound_properties p USING (molregno)
            WHERE p.full_molformula IS NOT NULL AND p.full_molformula != ''
        """
        rows = conn.execute(sql)
        batch = []
        n = 0
        for chembl_id, formula in rows:
            batch.append((chembl_id, formula))
            if len(batch) >= 10000:
                out.executemany("INSERT OR REPLACE INTO chembl_compounds VALUES (?, ?)", batch)
                n += len(batch); batch = []
        if batch:
            out.executemany("INSERT OR REPLACE INTO chembl_compounds VALUES (?, ?)", batch)
            n += len(batch)
        src = "compound_properties.full_molformula"
    else:
        # RDKit fallback: derive Hill formula from canonical SMILES
        from rdkit import Chem
        from rdkit.Chem import rdMolDescriptors
        sql = """
            SELECT m.chembl_id, s.canonical_smiles
            FROM molecule_dictionary m
            JOIN compound_structures s USING (molregno)
            WHERE s.canonical_smiles IS NOT NULL
        """
        rows = conn.execute(sql)
        batch, n, skipped = [], 0, 0
        for chembl_id, smi in rows:
            mol = Chem.MolFromSmiles(smi)
            if mol is None:
                skipped += 1
                continue
            formula = rdMolDescriptors.CalcMolFormula(mol)
            batch.append((chembl_id, formula))
            if len(batch) >= 10000:
                out.executemany("INSERT OR REPLACE INTO chembl_compounds VALUES (?, ?)", batch)
                n += len(batch); batch = []
        if batch:
            out.executemany("INSERT OR REPLACE INTO chembl_compounds VALUES (?, ?)", batch)
            n += len(batch)
        log(f"RDKit-derived rows: {n} (skipped unparsable: {skipped})")
        src = "compound_structures.canonical_smiles via RDKit CalcMolFormula"

    out.execute("CREATE INDEX idx_formula ON chembl_compounds(formula)")
    out.execute("ANALYZE")
    out.commit()
    count = out.execute("SELECT COUNT(*) FROM chembl_compounds").fetchone()[0]
    caffeine = [r[0] for r in out.execute(
        "SELECT chembl_id FROM chembl_compounds WHERE formula=? ORDER BY CAST(SUBSTR(chembl_id,7) AS INTEGER)",
        (SELF_CHECK_FORMULA,))]
    out.close()
    log(f"built {count} rows in {time.time()-t0:.0f}s; caffeine[{SELF_CHECK_FORMULA}] -> {caffeine}")
    if "CHEMBL113" not in caffeine:
        log("ERROR: self-check failed (CHEMBL113 caffeine missing)"); return 3

    tmp_db.rename(out_db)
    conn.close()

    meta = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chembl_version": v,
        "source_url": url,
        "tarball_md5_source_check": "see raw/ when kept" ,
        "formula_source": src,
        "rows": count,
        "self_check": {SELF_CHECK_FORMULA: caffeine},
        "tool": "scripts/build_chembl_local_mirror.py",
    }
    (ver_dir / "build_metadata.json").write_text(json.dumps(meta, indent=1))

    if args.keep_raw:
        raw_dir = ver_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        if tgz.exists():
            tgz.rename(raw_dir / tgz.name)

    # cleanup big extraction (always) + tarball (unless kept)
    import shutil
    shutil.rmtree(extract_dir, ignore_errors=True)
    if not args.keep_raw and tgz.exists():
        tgz.unlink()

    # atomic activation
    link = root / "current"
    tmp_link = root / ".current.tmp"
    if tmp_link.exists() or tmp_link.is_symlink():
        tmp_link.unlink()
    tmp_link.symlink_to(ver_dir.name)
    tmp_link.rename(link)
    log(f"activated: current -> {ver_dir.name}")
    log("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
