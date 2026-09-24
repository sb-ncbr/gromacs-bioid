#!/usr/bin/env python3
"""Populate the PubChem local mirror with atomic staging + symlink swap.

Downloads PubChem Compound/Extras flat files (CID-SMILES, CID-InChI-Key),
verifies md5 sidecars, builds the SQLite lookup DB via
``src_new.chemistry.pubchem_db.build``, validates, and atomically activates the
new version via a ``current`` symlink. Mirrors the lifecycle of
``populate_blast_databases.py``.

Run inside the k8s Job defined in ``k8s/pubchem-mirror-build-job.yaml`` or
manually: ``python scripts/populate_pubchem_mirror.py --target-dir /path``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = "https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras"

# Ordered manifest: (filename, required). Sizes recorded at populate time.
MANIFEST: list[tuple[str, bool]] = [
    ("CID-SMILES.gz", True),
    ("CID-InChI-Key.gz", True),
]

USER_AGENT = "bat3-pubchem-mirror/1.0 (local research mirror; contact: bat3 admin)"


def log(msg: str) -> None:
    """Print timestamped log message to stderr."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", file=sys.stderr)


def _file_md5(path: Path) -> str:
    """Calculate MD5 hash of a file."""
    md5_hash = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def _head(url: str) -> dict:
    """HEAD request -> {'size': int|None, 'last_modified': str|None}."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return {
            "size": resp.headers.get("Content-Length"),
            "last_modified": resp.headers.get("Last-Modified"),
        }


def _download(url: str, dest: Path, expected_md5: str | None = None) -> bool:
    """Download url -> dest (.part + resume on Range), verify md5 when given.

    Returns True on success. Retries: up to 3 rounds; later rounds resume
    from the existing .part size if the server honors Range requests.
    """
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, 4):
        headers = {"User-Agent": USER_AGENT}
        resume_from = part.stat().st_size if part.exists() else 0
        if resume_from > 0 and attempt > 1:
            headers["Range"] = f"bytes={resume_from}-"
            log(f"Resuming {dest.name} at byte {resume_from} (attempt {attempt})")
        else:
            resume_from = 0
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=300) as resp:
                # Server ignored Range -> restart from scratch.
                if resume_from and resp.status == 200:
                    resume_from = 0
                mode = "ab" if resume_from else "wb"
                with open(part, mode) as fh:
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        fh.write(chunk)
            part.replace(dest)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            log(f"Download error for {url} (attempt {attempt}): {exc}")
            time.sleep(10 * attempt)
            continue
        if expected_md5 is not None:
            actual = _file_md5(dest)
            if actual != expected_md5:
                log(f"MD5 mismatch for {dest.name}: expected {expected_md5}, got {actual}")
                dest.unlink(missing_ok=True)
                continue
            log(f"MD5 OK for {dest.name}")
        return True
    log(f"ERROR: giving up on {url} after retries")
    return False


def _fetch_md5(url: str, dest: Path) -> str | None:
    """Download '<file>.md5' sidecar and parse the hex digest."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode().strip()
        dest.write_text(text + "\n")
        return text.split()[0]
    except (urllib.error.URLError, OSError, IndexError) as exc:
        log(f"No usable md5 sidecar at {url}: {exc}")
        return None


def create_staging_dir(target_dir: Path) -> Path:
    """Create staging dir target/.staging/pubchem-<timestamp>."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    staging_dir = target_dir / ".staging" / f"pubchem-{timestamp}"
    staging_dir.mkdir(parents=True, exist_ok=False)
    log(f"Created staging directory: {staging_dir}")
    return staging_dir


def _activate(target_dir: Path, version_dir: Path) -> None:
    """Point 'current' symlink at version_dir atomically."""
    tmp_link = target_dir / ".current.tmp"
    tmp_link.unlink(missing_ok=True)
    tmp_link.symlink_to(version_dir.name)
    tmp_link.replace(target_dir / "current")
    log(f"Activated: current -> {version_dir.name}")


def _prune_old_versions(target_dir: Path, keep: int = 2) -> None:
    """Keep the newest `keep` version dirs (never the one 'current' points at)."""
    versions = sorted(
        (p for p in target_dir.glob("v*") if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )
    current = (target_dir / "current").resolve()
    for old in versions[keep:]:
        if old == current:
            continue
        log(f"Pruning old version: {old.name}")
        for child in sorted(old.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        old.rmdir()


def validate_db(db_path: Path, min_rows: int) -> list[str]:
    """Sanity-check the built DB. Returns list of failures (empty = OK)."""
    import sqlite3

    failures: list[str] = []
    if not db_path.exists():
        return [f"DB not found: {db_path}"]
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
        if rows < min_rows:
            failures.append(f"row count {rows} < expected minimum {min_rows}")
        for cid, expect_smiles in [(702, True), (2244, True), (5957, True)]:
            row = conn.execute("SELECT smiles FROM compounds WHERE cid=?", (cid,)).fetchone()
            if (row is not None) != expect_smiles:
                failures.append(f"probe CID {cid}: expected row={expect_smiles}, got {row is not None}")
        quick = conn.execute("PRAGMA quick_check(1000)").fetchone()[0]
        if quick != "ok":
            failures.append(f"quick_check: {quick}")
        conn.close()
    except Exception as exc:  # noqa: BLE001 - report as validation failure
        failures.append(f"validation exception: {exc}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-dir", default="/app/databases/pubchem",
                        help="Mirror root (contains v* dirs and 'current' symlink)")
    parser.add_argument("--version-label", default=None,
                        help="Version dir label (default: UTC date vYYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Build only the first N CIDs (sample builds)")
    parser.add_argument("--no-build", action="store_true",
                        help="Download + verify only; skip SQLite build")
    parser.add_argument("--skip-download", action="store_true",
                        help="Reuse raw files already in a staging dir")
    parser.add_argument("--staging-dir", default=None,
                        help="Reuse an explicit staging dir (resume after failure)")
    parser.add_argument("--keep-raw", action="store_true", default=True,
                        help="Retain raw .gz files inside the version dir (default: keep)")
    args = parser.parse_args(argv)

    target_dir = Path(args.target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if args.staging_dir:
        staging_dir = Path(args.staging_dir)
        if not staging_dir.is_dir():
            log(f"ERROR: --staging-dir does not exist: {staging_dir}")
            return 2
    else:
        staging_dir = create_staging_dir(target_dir)
    raw_dir = staging_dir / "raw"
    raw_dir.mkdir(exist_ok=True)

    metadata: dict = {
        "sources": {},
        "limit": args.limit,
        "started": datetime.now(timezone.utc).isoformat(),
    }

    # ---- Phase 1: download + verify ------------------------------------------
    for filename, required in MANIFEST:
        url = f"{BASE_URL}/{filename}"
        dest = raw_dir / filename
        if dest.exists():
            log(f"Already present, skipping download: {dest.name}")
            metadata["sources"][filename] = {"url": url, "reused": True}
            continue
        try:
            head = _head(url)
        except Exception as exc:
            log(f"ERROR: HEAD failed for {url}: {exc}")
            return 1
        log(f"{filename}: {head['size']} bytes, last-modified {head['last_modified']}")
        md5 = _fetch_md5(f"{url}.md5", raw_dir / f"{filename}.md5")
        if md5 is None and required:
            log(f"ERROR: md5 sidecar missing for required file {filename}")
            return 1
        if not _download(url, dest, expected_md5=md5):
            log(f"ERROR: download failed for required file {filename}")
            return 1
        metadata["sources"][filename] = {
            "url": url, "size": head["size"],
            "last_modified": head["last_modified"], "md5": md5,
        }

    if args.no_build:
        log("--no-build requested; leaving staging dir in place")
        print(staging_dir)
        return 0

    # ---- Phase 2: build SQLite -----------------------------------------------
    from src_new.molecules.pubchem_db import build

    log("Starting SQLite build (this is the long phase; checkpoints every 5M rows)")
    build_stats = build(
        db_path=staging_dir / "pubchem.sqlite",
        smiles_gz=raw_dir / "CID-SMILES.gz",
        inchikey_gz=raw_dir / "CID-InChI-Key.gz",
        limit=args.limit,
    )
    metadata["build"] = build_stats

    # ---- validate -------------------------------------------------------------
    min_rows = 1000 if args.limit else 100_000_000
    failures = validate_db(staging_dir / "pubchem.sqlite", min_rows=min_rows)
    if failures:
        for f in failures:
            log(f"VALIDATION FAILURE: {f}")
        return 1
    log("Validation passed")

    # ---- activate -------------------------------------------------------------
    label = args.version_label or f"v{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
    version_dir = target_dir / label
    if version_dir.exists():
        log(f"ERROR: version dir already exists: {version_dir}")
        return 1
    metadata["finished"] = datetime.now(timezone.utc).isoformat()
    with open(staging_dir / "build_metadata.json", "w") as fh:
        json.dump(metadata, fh, indent=2)
    staging_dir.rename(version_dir)
    # staging parent may linger; harmless
    _activate(target_dir, version_dir)
    _prune_old_versions(target_dir, keep=2)
    log(f"DONE: {version_dir} active")
    return 0


if __name__ == "__main__":
    sys.exit(main())
