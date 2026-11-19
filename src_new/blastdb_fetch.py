"""Download one NCBI BLAST database snapshot from NCBI's AWS copy (2026-11-19).

    python -m src_new.blastdb_fetch <db> <snapshot> <dest_dir> [--streams 8]

NCBI keeps the last few snapshots of its BLAST databases in the public bucket
s3://ncbi-blast-databases/<snapshot>/ (e.g. 2026-10-22-01-05-01), as the
volume files themselves (no archives). Downloading a named snapshot, not
"latest", lets the NFS copy and the BLAST services' NVMe copies fetch the
same release in parallel: both name it release_name(db, snapshot), e.g.
nr-20261022-010501, the name the workers compare (blast_service_client).

Measured 2026-11-19 from the cluster: 26 MB/s per stream, 171 MB/s with 8;
NCBI's FTP gave 2 MB/s.

Each file is written as <name>.part and renamed once its size matches the
server's, so a rerun resumes per file. When every file is there, `blastdbcmd
-info` must read the database, and <dest>/.complete is written.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger("blastdb_fetch")

BUCKET = "https://ncbi-blast-databases.s3.amazonaws.com"
#: taxonomy files BLAST reads next to the database (as in the NFS copies)
EXTRA = ("taxdb.btd", "taxdb.bti", "taxonomy4blast.sqlite3")
COMPLETE = ".complete"
CHUNK = 8 << 20
ATTEMPTS = 6


def release_name(db: str, snapshot: str) -> str:
    """nr + 2026-10-22-01-05-01 -> nr-20261022-010501 (the NFS naming)."""
    d = snapshot.replace("-", "")
    return f"{db}-{d[:8]}-{d[8:14]}"


def _get(url: str, timeout: float = 60):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bioid-blastdb-fetch"}),
                                  timeout=timeout)


def metadata(db: str, snapshot: str) -> dict:
    for kind in ("prot", "nucl"):
        try:
            with _get(f"{BUCKET}/{snapshot}/{db}-{kind}-metadata.json") as r:
                meta = json.load(r)
            meta["_name"] = f"{db}-{kind}-metadata.json"
            return meta
        except urllib.error.HTTPError as exc:
            if exc.code not in (403, 404):
                raise
    raise RuntimeError(f"{db} is not in snapshot {snapshot}")


def files(meta: dict) -> list[str]:
    return [f.rsplit("/", 1)[-1] for f in meta["files"]] + list(EXTRA)


def _download(url: str, target: Path, progress: Callable[[int], None]) -> int:
    part = target.with_name(target.name + ".part")
    for attempt in range(1, ATTEMPTS + 1):
        got = 0
        try:
            with _get(url) as r, open(part, "wb") as out:
                size = int(r.headers.get("Content-Length") or -1)
                while True:
                    buf = r.read(CHUNK)
                    if not buf:
                        break
                    out.write(buf)
                    got += len(buf)
                    progress(len(buf))
            if size >= 0 and got != size:
                raise IOError(f"got {got} of {size} bytes")
            os.replace(part, target)
            return got
        except Exception as exc:
            progress(-got)
            if attempt == ATTEMPTS:
                raise RuntimeError(f"{target.name}: {exc}") from exc
            log.warning("%s: %s (attempt %d), retrying", target.name, exc, attempt)
            time.sleep(min(60, 5 * attempt))
    return 0


def fetch(db: str, snapshot: str, dest: Path, streams: int = 8,
          status: Optional[dict] = None, lock: Optional[threading.Lock] = None) -> int:
    """Download the snapshot into dest; `status` (optional) gets done_bytes,
    total_bytes, files_done, files_total as it goes. Returns the bytes."""
    status = {} if status is None else status
    lock = lock or threading.Lock()
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    meta = metadata(db, snapshot)
    names = files(meta)
    have = {n: (dest / n).stat().st_size for n in names if (dest / n).exists()}
    with lock:
        status.update(release=dest.name, snapshot=snapshot, source="aws",
                      total_bytes=int(meta.get("bytes-total") or 0), done_bytes=sum(have.values()),
                      files_total=len(names), files_done=len(have), started=time.time())

    def progress(n: int) -> None:
        with lock:
            status["done_bytes"] += n

    def one(name: str) -> None:
        _download(f"{BUCKET}/{snapshot}/{name}", dest / name, progress)
        with lock:
            status["files_done"] += 1

    todo = [n for n in names if n not in have]
    with ThreadPoolExecutor(max_workers=max(1, streams)) as pool:
        for f in [pool.submit(one, n) for n in todo]:
            f.result()  # the first failure stops the fetch (rerun resumes)
    (dest / meta["_name"]).write_text(json.dumps({k: v for k, v in meta.items() if k != "_name"}))
    info = subprocess.run(["blastdbcmd", "-db", str(dest / db), "-info"],
                          capture_output=True, text=True, timeout=600)
    if info.returncode != 0:
        raise RuntimeError(f"blastdbcmd cannot read {dest / db}: {info.stderr.strip()[:300]}")
    total = sum((dest / n).stat().st_size for n in names)
    (dest / COMPLETE).write_text(json.dumps({"snapshot": snapshot, "files": len(names), "bytes": total,
                                             "info": info.stdout.strip().splitlines()[:4],
                                             "finished": time.strftime("%FT%T")}))
    with lock:
        status.update(done_bytes=total, total_bytes=total, finished=time.time())
    log.info("%s: %d files, %.1f GB", dest, len(names), total / 1e9)
    return total


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("db")
    p.add_argument("snapshot")
    p.add_argument("dest", help="directory, e.g. /app/databases/.staging/nr-20261022-010501")
    p.add_argument("--streams", type=int, default=8)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    status: dict = {}
    lock = threading.Lock()
    done = threading.Event()

    def report() -> None:
        while not done.wait(60):
            with lock:
                s = dict(status)
            if s.get("total_bytes"):
                log.info("%.1f/%.1f GB, %d/%d files", s["done_bytes"] / 1e9, s["total_bytes"] / 1e9,
                         s["files_done"], s["files_total"])

    threading.Thread(target=report, daemon=True).start()
    fetch(a.db, a.snapshot, Path(a.dest), a.streams, status, lock)
    done.set()


if __name__ == "__main__":
    main()
