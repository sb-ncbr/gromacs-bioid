"""Download one NCBI BLAST database snapshot from NCBI's AWS copy (2026-11-19).

    python -m src_new.blastdb_fetch <db> <snapshot> <dest_dir> [--streams 8]

NCBI keeps the last few snapshots of its BLAST databases in the public bucket
s3://ncbi-blast-databases/<snapshot>/ (e.g. 2026-10-22-01-05-01), as the
volume files themselves (no archives). Downloading a named snapshot, not
"latest", lets the NFS copy and the BLAST services' NVMe copies fetch the
same release in parallel: both name it release_name(db, snapshot), e.g.
nr-20261022-010501, the name the workers compare (blast_service_client).

The same snapshots are on Google Cloud Storage (gs://blast-db), byte for
byte (checked by MD5 2026-11-19), and that is the default source: Google
serves it from a European edge, while the route from the cluster to AWS
us-east-1 and NCBI degrades during the day (2026-11-19 from 08:35: S3 0.3 MB/s
per stream, Google 17 MB/s per stream, 287 MB/s with 16). BLAST_FETCH_BUCKET
chooses another copy, e.g. https://ncbi-blast-databases.s3.amazonaws.com.
Google's answers carry each file's MD5 (x-goog-hash); a file fetched in one
piece is checked against it.

Each file is written as <name>.part and renamed once its size matches the
server's, so a rerun resumes per file. Files larger than PIECE_BYTES (the
index files: nr.pdb is 101 GB) are fetched in pieces with HTTP ranges, spread
over all streams like small files, and the finished pieces are listed in
<name>.part.json, so a rerun resumes per piece (2026-11-19: one stream per
file left nr.pdb at 5 MB/s, and a stalled stream restarted it from zero). A
.part from before has a valid prefix: its whole pieces count as done. When
every file is there, `blastdbcmd -info` must read the database, and
<dest>/.complete is written.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
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

BUCKET = os.environ.get("BLAST_FETCH_BUCKET", "https://storage.googleapis.com/blast-db")
#: taxonomy files BLAST reads next to the database (as in the NFS copies)
EXTRA = ("taxdb.btd", "taxdb.bti", "taxonomy4blast.sqlite3")
COMPLETE = ".complete"
CHUNK = 8 << 20
ATTEMPTS = 6
PIECE_BYTES = 1 << 30


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
            md5 = hashlib.md5()
            with _get(url) as r, open(part, "wb") as out:
                size = int(r.headers.get("Content-Length") or -1)
                want = _md5_header(r.headers)
                while True:
                    buf = r.read(CHUNK)
                    if not buf:
                        break
                    out.write(buf)
                    md5.update(buf)
                    got += len(buf)
                    progress(len(buf))
            if size >= 0 and got != size:
                raise IOError(f"got {got} of {size} bytes")
            if want and base64.b64encode(md5.digest()).decode() != want:
                raise IOError("MD5 differs from the server's")
            os.replace(part, target)
            return got
        except Exception as exc:
            progress(-got)
            if attempt == ATTEMPTS:
                raise RuntimeError(f"{target.name}: {exc}") from exc
            log.warning("%s: %s (attempt %d), retrying", target.name, exc, attempt)
            time.sleep(min(60, 5 * attempt))
    return 0


def _md5_header(headers) -> str:
    """The base64 MD5 in Google's x-goog-hash header ("crc32c=..., md5=...")."""
    for h in headers.get_all("x-goog-hash") or []:
        for part in h.split(","):
            k, _, v = part.strip().partition("=")
            if k == "md5":
                return v
    return ""


def _size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "bioid-blastdb-fetch"})
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return int(r.headers["Content-Length"])
        except Exception:
            if attempt == ATTEMPTS:
                raise
            time.sleep(5 * attempt)
    return 0


class _Pieces:
    """One large file fetched in PIECE_BYTES ranges into <name>.part."""

    def __init__(self, url: str, target: Path, size: int) -> None:
        self.url, self.target, self.size = url, target, size
        self.part = target.with_name(target.name + ".part")
        self.state = target.with_name(target.name + ".part.json")
        self.lock = threading.Lock()
        offsets = range(0, size, PIECE_BYTES)
        try:
            done = set(json.loads(self.state.read_text())["done"])
        except (OSError, ValueError, KeyError):
            # no piece list: a .part written front to back by _download
            have = self.part.stat().st_size if self.part.exists() else 0
            done = {o for o in offsets if o + min(PIECE_BYTES, size - o) <= have}
        self.done = done
        self.todo = [o for o in offsets if o not in done]
        # The piece list goes to disk BEFORE the .part grows to full size: a
        # full-size .part without a list would read as a finished front-to-back
        # download on the next start (2026-11-19: ~1,000 nt volumes and nr's
        # indexes were renamed as complete while all zeros).
        self._save()
        with open(self.part, "ab") as f:
            f.truncate(size)

    def _save(self) -> None:
        tmp = self.state.with_name(self.state.name + ".tmp")
        tmp.write_text(json.dumps({"size": self.size, "done": sorted(self.done)}))
        os.replace(tmp, self.state)

    def done_bytes(self) -> int:
        return sum(min(PIECE_BYTES, self.size - o) for o in self.done)

    def fetch(self, offset: int, progress: Callable[[int], None]) -> bool:
        """One piece; True when it was the last one (the file is complete)."""
        length = min(PIECE_BYTES, self.size - offset)
        for attempt in range(1, ATTEMPTS + 1):
            got = 0
            try:
                req = urllib.request.Request(self.url, headers={
                    "User-Agent": "bioid-blastdb-fetch", "Range": f"bytes={offset}-{offset + length - 1}"})
                with urllib.request.urlopen(req, timeout=60) as r, open(self.part, "r+b") as out:
                    if r.status != 206:
                        raise IOError(f"HTTP {r.status} for a range request")
                    out.seek(offset)
                    while got < length:
                        buf = r.read(min(CHUNK, length - got))
                        if not buf:
                            break
                        out.write(buf)
                        got += len(buf)
                        progress(len(buf))
                if got != length:
                    raise IOError(f"got {got} of {length} bytes at {offset}")
                break
            except Exception as exc:
                progress(-got)
                if attempt == ATTEMPTS:
                    raise RuntimeError(f"{self.target.name} @{offset}: {exc}") from exc
                log.warning("%s @%d: %s (attempt %d), retrying", self.target.name, offset, exc, attempt)
                time.sleep(min(60, 5 * attempt))
        with self.lock:
            self.done.add(offset)
            self._save()
            return self.finish()

    def finish(self) -> bool:
        """Rename the .part once every piece is there."""
        if len(self.done) < len(range(0, self.size, PIECE_BYTES)):
            return False
        os.replace(self.part, self.target)
        self.state.unlink(missing_ok=True)
        return True


def _has_holes(path: Path, check: str, url: str) -> bool:
    """Whether a downloaded file is not all data.

    "blocks" (NFS/GPFS, no compression): a file larger than 64 MB must have
    its whole size allocated; a never-written region is a hole. "md5" (the
    NVMe copies on compressing ZFS, where allocation says nothing): a file
    larger than PIECE_BYTES must have the server's MD5 (local disk reads are
    fast; smaller files were checked while downloading)."""
    size = path.stat().st_size
    if check == "blocks":
        return size > 64 << 20 and path.stat().st_blocks * 512 < 0.97 * size
    if check == "md5" and size > PIECE_BYTES:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "bioid-blastdb-fetch"})
        with urllib.request.urlopen(req, timeout=60) as r:
            want = _md5_header(r.headers)
        if not want:
            return False
        md5 = hashlib.md5()
        with open(path, "rb") as f:
            for buf in iter(lambda: f.read(CHUNK), b""):
                md5.update(buf)
        return base64.b64encode(md5.digest()).decode() != want
    return False


def fetch(db: str, snapshot: str, dest: Path, streams: int = 8,
          status: Optional[dict] = None, lock: Optional[threading.Lock] = None,
          check: str = "blocks", _again: bool = False) -> int:
    """Download the snapshot into dest; `status` (optional) gets done_bytes,
    total_bytes, files_done, files_total as it goes. Returns the bytes.
    `check` is how finished files are checked for never-written regions
    (_has_holes): "blocks", "md5" or "none"."""
    status = {} if status is None else status
    lock = lock or threading.Lock()
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / COMPLETE).unlink(missing_ok=True)  # complete again only once checked below
    meta = metadata(db, snapshot)
    names = files(meta)
    have = {n: (dest / n).stat().st_size for n in names if (dest / n).exists()}
    with lock:
        status.update(release=dest.name, snapshot=snapshot, source=BUCKET,
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
    sizes: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=max(1, streams)) as pool:
        for n, size in zip(todo, pool.map(lambda n: _size(f"{BUCKET}/{snapshot}/{n}"), todo)):
            sizes[n] = size
    big = {n: _Pieces(f"{BUCKET}/{snapshot}/{n}", dest / n, sizes[n])
           for n in todo if sizes[n] > PIECE_BYTES}
    with lock:
        status["done_bytes"] += sum(p.done_bytes() for p in big.values())
        status["files_done"] += sum(1 for p in big.values() if not p.todo and p.finish())

    def piece(p: _Pieces, offset: int) -> None:
        if p.fetch(offset, progress):
            with lock:
                status["files_done"] += 1

    with ThreadPoolExecutor(max_workers=max(1, streams)) as pool:
        jobs = [pool.submit(piece, p, o) for p in big.values() for o in p.todo]
        jobs += [pool.submit(one, n) for n in todo if n not in big]
        for f in jobs:
            f.result()  # the first failure stops the fetch (rerun resumes)
    with ThreadPoolExecutor(max_workers=max(1, streams)) as pool:
        flags = list(pool.map(lambda n: _has_holes(dest / n, check, f"{BUCKET}/{snapshot}/{n}"), names))
    holes = [n for n, bad in zip(names, flags) if bad]
    if holes:
        for n in holes:
            (dest / n).unlink()
        listed = ", ".join(holes[:5]) + (", ..." if len(holes) > 5 else "")
        if _again:
            raise RuntimeError(f"{len(holes)} files still incomplete after fetching them again: {listed}")
        log.warning("%d files were incomplete (%s): removed, fetching them again", len(holes), listed)
        return fetch(db, snapshot, dest, streams, status, lock, check, _again=True)
    (dest / meta["_name"]).write_text(json.dumps({k: v for k, v in meta.items() if k != "_name"}))
    info = subprocess.run(["blastdbcmd", "-db", str(dest / db), "-info"],
                          capture_output=True, text=True, timeout=600)
    if info.returncode != 0:
        raise RuntimeError(f"blastdbcmd cannot read {dest / db}: {info.stderr.strip()[:300]}")
    total = sum((dest / n).stat().st_size for n in names)
    (dest / COMPLETE).write_text(json.dumps({"snapshot": snapshot, "checked": check,
                                             "files": len(names), "bytes": total,
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
    p.add_argument("--check", choices=("blocks", "md5", "none"), default="blocks",
                   help="how finished files are checked for never-written regions")
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
    fetch(a.db, a.snapshot, Path(a.dest), a.streams, status, lock, check=a.check)
    done.set()


if __name__ == "__main__":
    main()
