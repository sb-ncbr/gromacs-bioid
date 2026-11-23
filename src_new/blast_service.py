"""One BLAST database on a node-local NVMe volume, as an HTTP service (2026-11-19).

    python -m src_new.blast_service      (deploy/bioid-blast-<db>.yaml)

Workers send nr / nt / core_nt / UniRef50 searches here when the service is
ready (identification/resolvers/blast_service_client.py); otherwise they
search the NFS copy. On start the service copies the database release the
NFS symlink points to onto its volume (rate-capped: NFS is shared with every
worker), checks the sizes, then serves it. A restarted pod finds the copy
complete and is ready at once. When the NFS symlink moves to a new release,
the old copy keeps serving (workers see the release differ and search NFS)
while the new one is copied; the old copy is removed once the new one is
complete.

Same image, same BLAST binary and same database files as the workers, so a
search here returns what it would on NFS (checked 2026-11-18 on nr: same 3
identity hits and 2,980 similarity hits, same order and scores).

Env:
    BLAST_DB_PATH     the database as workers name it, e.g. /app/databases/nr/nr
    BLAST_LOCAL_DIR   the NVMe volume (default /nvme)
    BLAST_THREADS     threads per search (default 8)
    BLAST_SLOTS       searches at a time (default 1; nr reads the whole volume
                      per search, so more at once only share its bandwidth)
    BLAST_STAGE_MBPS  copy rate cap in MB/s (default 40)
    BLAST_FETCH_SNAPSHOT  download this NCBI AWS snapshot (blastdb_fetch) instead
                      of copying from NFS; served once NFS points to the same
                      release (database updates: both download in parallel)
    BLAST_FETCH_STREAMS   parallel downloads (default 8)
    PORT              (default 8080)

GET /health: {db, release, source_release, state (staging|ready|error),
staging {release, done_bytes, total_bytes, files_done, files_total},
blast_version, running, waiting, searches, timeouts, failures, abandoned, error}.
POST /search {release, query, task, max_target_seqs, timeout_s}: 200
{release, seconds, output: <-outfmt 15 report>}; 409 not ready or another
release; 422 bad request; 504 out of time; 500 BLAST failed; 499 the client
closed the connection (a cancelled run) while it waited or ran, and the search
was stopped (2026-11-23).
"""
from __future__ import annotations

import json
import logging
import os
import re
import select
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("blast_service")

COMPLETE = ".complete"
CHUNK = 8 << 20
MAX_TIMEOUT_S = 43200
MAX_QUERY = 100_000
TASKS = {"blastp": {None, "blastp-short"}, "blastn": {None, "blastn-short"}}
QUERY_RE = re.compile(r"^[A-Za-z*\-]+$")
RECHECK_S = 60
#: how often a waiting or running search checks that its client is still there
POLL_S = 5.0


class Service:
    def __init__(self, db_path: str, local_dir: str, threads: int = 8, slots: int = 1,
                 stage_mbps: float = 40.0, snapshot: Optional[str] = None, streams: int = 8) -> None:
        from .blastdb_fetch import release_name
        self.db_path = db_path
        self.db_name = os.path.basename(db_path)
        self.local = Path(local_dir)
        self.threads = threads
        self.stage_bps = stage_mbps * 1e6
        self.slots = threading.BoundedSemaphore(max(1, slots))
        self.lock = threading.Lock()
        self.release: Optional[str] = None
        # AWS snapshot to download ahead of the NFS switch (blastdb_fetch)
        self.snapshot = snapshot
        self.prefetch = release_name(self.db_name, snapshot) if snapshot else None
        self.streams = streams
        self.staging: dict[str, Any] = {}
        self.error = ""
        self.counts = {"running": 0, "waiting": 0, "searches": 0, "timeouts": 0, "failures": 0,
                       "abandoned": 0}
        self.program = "blastp" if self._is_protein() else "blastn"
        self.blast_version = self._version()
        complete = [d.name for d in self._copies() if self._complete(d.name)]
        want = self.source_release()
        self.release = want if want in complete else (complete[-1] if complete else None)

    # -- the database -----------------------------------------------------------

    def source_dir(self) -> Path:
        return Path(os.path.realpath(os.path.dirname(self.db_path)))

    def source_release(self) -> str:
        return self.source_dir().name

    def _is_protein(self) -> bool:
        src = self.source_dir()
        return any((src / f"{self.db_name}{ext}").exists() for ext in (".pal", ".pin", ".psq", ".00.pin"))

    def _version(self) -> str:
        try:
            out = subprocess.run([self.program, "-version"], capture_output=True, text=True, timeout=30)
            return (out.stdout or "").strip().splitlines()[0]
        except Exception:
            return ""

    def _copies(self) -> list[Path]:
        if not self.local.is_dir():
            return []
        return sorted(p for p in self.local.iterdir() if p.is_dir() and not p.name.startswith("."))

    def _complete(self, release: str) -> bool:
        marker = self.local / release / COMPLETE
        if not marker.exists():
            return False
        if release != self.prefetch:
            return True
        # a downloaded copy counts once its files were checked for holes
        # (blastdb_fetch since 2026-11-19; an older marker is checked again)
        try:
            return json.loads(marker.read_text()).get("checked") in ("md5", "blocks")
        except (OSError, ValueError):
            return False

    def state(self) -> str:
        if self.release:
            return "ready"
        return "error" if self.error else "staging"

    def health(self) -> dict[str, Any]:
        source = self.source_release()
        with self.lock:
            return {"db": self.db_name, "release": self.release, "prefetch": self.prefetch,
                    "source_release": source, "state": self.state(),
                    "staging": dict(self.staging), "blast_version": self.blast_version,
                    "program": self.program, "threads": self.threads, "error": self.error,
                    **self.counts}

    # -- copying ----------------------------------------------------------------

    def stage(self, release: Optional[str] = None) -> None:
        """Copy the release the NFS symlink points to; resumable per file."""
        src = self.source_dir()
        release = release or src.name
        dst = self.local / release
        files = sorted(p for p in src.iterdir() if p.is_file())
        total = sum(p.stat().st_size for p in files)
        self.local.mkdir(parents=True, exist_ok=True)
        have = sum((dst / p.name).stat().st_size for p in files if (dst / p.name).exists())
        if shutil.disk_usage(self.local).free < (total - have) * 1.05:
            # no room next to the old copy: drop it (workers search NFS meanwhile)
            with self.lock:
                self.release = None
            for old in self._copies():
                if old.name != release:
                    shutil.rmtree(old, ignore_errors=True)
        dst.mkdir(parents=True, exist_ok=True)
        with self.lock:
            self.staging = {"release": release, "done_bytes": 0, "total_bytes": total,
                            "files_done": 0, "files_total": len(files), "started": time.time()}
        done = 0
        for i, f in enumerate(files, 1):
            size = f.stat().st_size
            target = dst / f.name
            if not (target.exists() and target.stat().st_size == size):
                self._copy(f, target, done)
            done += size
            with self.lock:
                self.staging.update(done_bytes=done, files_done=i)
        bad = [f.name for f in files if (dst / f.name).stat().st_size != f.stat().st_size]
        if bad:
            raise RuntimeError(f"size differs after copy: {bad[:5]}")
        (dst / COMPLETE).write_text(json.dumps({"files": len(files), "bytes": total,
                                                "finished": time.strftime("%FT%T")}))
        with self.lock:
            self.release = release
            self.staging["finished"] = time.time()
            self.error = ""
        for old in self._copies():
            if old.name != release:
                shutil.rmtree(old, ignore_errors=True)
        log.info("ready: %s (%d files, %.1f GB)", release, len(files), total / 1e9)

    def _copy(self, src: Path, target: Path, done_before: int) -> None:
        part = target.with_name(target.name + ".part")
        started, copied = time.time(), 0
        with open(src, "rb") as fi, open(part, "wb") as fo:
            while True:
                buf = fi.read(CHUNK)
                if not buf:
                    break
                fo.write(buf)
                copied += len(buf)
                with self.lock:
                    self.staging["done_bytes"] = done_before + copied
                ahead = copied / self.stage_bps - (time.time() - started)
                if ahead > 0:
                    time.sleep(ahead)
        os.replace(part, target)

    def keep_current(self) -> None:
        """Copy the release NFS points to, at start and whenever the symlink
        moves. With a snapshot (BLAST_FETCH_SNAPSHOT), download that from AWS
        instead and serve it once NFS points to the same release: the NFS
        copy is downloaded in parallel, then the symlink is switched."""
        while True:
            want = self.source_release()
            try:
                if self.prefetch and not self._complete(self.prefetch):
                    self._drop(keep={self.release, self.prefetch})
                    self.fetch_snapshot()
                if self._complete(want):
                    if self.release != want:
                        with self.lock:
                            self.release = want
                elif not self.prefetch:
                    self.stage(want)
                if self.prefetch:
                    self._drop(keep={self.release, self.prefetch})
            except Exception as exc:
                log.exception("getting %s failed", self.prefetch or want)
                with self.lock:
                    self.error = f"{self.prefetch or want}: {exc}"
            time.sleep(RECHECK_S)

    def fetch_snapshot(self) -> None:
        from . import blastdb_fetch
        with self.lock:
            self.error = ""
        blastdb_fetch.fetch(self.db_name, self.snapshot, self.local / self.prefetch,
                            self.streams, self.staging, self.lock, check="md5")
        log.info("downloaded %s; served once NFS points to it", self.prefetch)

    def _drop(self, keep: set) -> None:
        """Remove copies other than `keep` (old or partial releases)."""
        for d in self._copies():
            if d.name not in keep:
                log.info("removing %s", d.name)
                shutil.rmtree(d, ignore_errors=True)

    # -- searching --------------------------------------------------------------

    def search(self, req: dict[str, Any],
               gone: Optional[Callable[[], bool]] = None) -> tuple[int, dict[str, Any]]:
        """`gone()` is True once the client closed the connection (2026-11-23:
        a cancelled run's worker hangs up); the search then stops (499)."""
        release = self.release
        if not release or req.get("release") != release:
            return 409, {"error": f"serving {release}, asked for {req.get('release')}"}
        query = str(req.get("query") or "")
        task = req.get("task") or None
        try:
            max_targets = int(req.get("max_target_seqs") or 500)
            timeout_s = float(req.get("timeout_s") or 0)
        except (TypeError, ValueError):
            return 422, {"error": "max_target_seqs and timeout_s must be numbers"}
        if not QUERY_RE.match(query) or len(query) > MAX_QUERY:
            return 422, {"error": "query must be one sequence of letters"}
        if task not in TASKS[self.program]:
            return 422, {"error": f"task {task} is not one of {sorted(t for t in TASKS[self.program] if t)}"}
        if not 1 <= max_targets <= 5000 or not 0 < timeout_s <= MAX_TIMEOUT_S:
            return 422, {"error": "max_target_seqs 1-5000, timeout_s 1-43200"}
        deadline = time.time() + timeout_s
        with self.lock:
            self.counts["waiting"] += 1
        acquired = False
        while not acquired and time.time() < deadline:
            acquired = self.slots.acquire(timeout=max(0.0, min(POLL_S, deadline - time.time())))
            if not acquired and gone is not None and gone():
                with self.lock:
                    self.counts["waiting"] -= 1
                    self.counts["abandoned"] += 1
                return 499, {"error": "the client went away"}
        with self.lock:
            self.counts["waiting"] -= 1
        if not acquired:
            with self.lock:
                self.counts["timeouts"] += 1
            return 504, {"error": "timed out waiting for a free slot"}
        try:
            return self._run(release, query, task, max_targets, deadline, gone)
        finally:
            self.slots.release()

    def _run(self, release: str, query: str, task: Optional[str], max_targets: int,
             deadline: float, gone: Optional[Callable[[], bool]] = None) -> tuple[int, dict[str, Any]]:
        fd, out = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        cmd = [self.program, "-outfmt", "15", "-db", str(self.local / release / self.db_name),
               "-out", out, "-num_threads", str(self.threads), "-max_target_seqs", str(max_targets)]
        if task:
            cmd += ["-task", task]
        with self.lock:
            self.counts["running"] += 1
        started = time.time()
        try:
            r = _run_until(cmd, query, deadline, gone)
            if r is None:
                with self.lock:
                    self.counts["abandoned"] += 1
                return 499, {"error": "the client went away"}
            if r.returncode != 0:
                with self.lock:
                    self.counts["failures"] += 1
                return 500, {"error": f"BLAST exit {r.returncode}: {(r.stderr or '').strip()[:500]}"}
            with open(out) as f:
                report = json.load(f)
            with self.lock:
                self.counts["searches"] += 1
            return 200, {"release": release, "seconds": round(time.time() - started, 1), "output": report}
        except subprocess.TimeoutExpired:
            with self.lock:
                self.counts["timeouts"] += 1
            return 504, {"error": "BLAST ran out of time"}
        finally:
            with self.lock:
                self.counts["running"] -= 1
            if os.path.exists(out):
                os.unlink(out)


def _run_until(cmd: list[str], query: str, deadline: float,
               gone: Optional[Callable[[], bool]]) -> Optional[subprocess.CompletedProcess]:
    """subprocess.run with the deadline as timeout (TimeoutExpired), checking
    `gone()` every POLL_S: None when the client went away (BLAST killed).
    2026-11-23."""
    if gone is None:
        return subprocess.run(cmd, input=query, text=True, capture_output=True,
                              timeout=max(1.0, deadline - time.time()))
    with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True) as proc:
        pending: Optional[str] = query
        while True:
            left = max(1.0, deadline - time.time())
            try:
                out, err = proc.communicate(pending, timeout=min(POLL_S, left))
                return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
            except subprocess.TimeoutExpired:
                pending = None
                if gone():
                    proc.kill()
                    proc.communicate()
                    log.info("client went away; BLAST stopped")
                    return None
                if time.time() >= deadline:
                    proc.kill()
                    proc.communicate()
                    raise


def _client_gone(sock: socket.socket) -> bool:
    """True when the client closed its end (2026-11-23). The request was read
    in full, so a readable socket means end of stream (or a reset)."""
    try:
        readable, _, _ = select.select([sock], [], [], 0)
        return bool(readable) and sock.recv(1, socket.MSG_PEEK) == b""
    except (OSError, ValueError):
        return True


def make_handler(service: Service) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send(200, service.health())
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            if self.path != "/search":
                self._send(404, {"error": "not found"})
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(min(n, 1 << 20)) or b"{}")
            except (ValueError, TypeError):
                self._send(422, {"error": "body must be JSON"})
                return
            code, body = service.search(req if isinstance(req, dict) else {},
                                        gone=lambda: _client_gone(self.connection))
            self._send(code, body)

        def log_message(self, fmt: str, *args: Any) -> None:
            if not (args and str(args[0]).startswith("GET /health")):
                log.info("%s %s", self.address_string(), fmt % args)

    return Handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    service = Service(
        db_path=os.environ["BLAST_DB_PATH"],
        local_dir=os.environ.get("BLAST_LOCAL_DIR", "/nvme"),
        threads=int(os.environ.get("BLAST_THREADS", "8")),
        slots=int(os.environ.get("BLAST_SLOTS", "1")),
        stage_mbps=float(os.environ.get("BLAST_STAGE_MBPS", "40")),
        snapshot=os.environ.get("BLAST_FETCH_SNAPSHOT") or None,
        streams=int(os.environ.get("BLAST_FETCH_STREAMS", "8")),
    )
    threading.Thread(target=service.keep_current, daemon=True, name="stage").start()
    server = ThreadingHTTPServer(("", int(os.environ.get("PORT", "8080"))), make_handler(service))
    log.info("%s: %s, release %s", service.db_name, service.state(), service.release)
    server.serve_forever()


if __name__ == "__main__":
    main()
