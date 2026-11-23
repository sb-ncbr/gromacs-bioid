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
    BLAST_SLOTS       BLAST processes at a time (default 1; nr reads the whole volume
                      per search, so more at once only share its bandwidth)
    BLAST_STAGE_MBPS  copy rate cap in MB/s (default 40)
    BLAST_FETCH_SNAPSHOT  download this NCBI AWS snapshot (blastdb_fetch) instead
                      of copying from NFS; served once NFS points to the same
                      release (database updates: both download in parallel)
    BLAST_FETCH_STREAMS   parallel downloads (default 8)
    BLAST_BATCH_MAX   searches run as one BLAST process (default 16; 1 = off)
    BLAST_BATCH_WAIT_S  how long a search on an idle service waits for others
                      to join its batch (default 2)
    BLAST_BATCH_SPREAD  auto|1|0 (default auto): spread waiting searches over
                      free slots (1) or fill one batch first (0); auto = spread
                      when the database fits in the pod's memory (page cache)
    PORT              (default 8080)

GET /health: {db, release, source_release, state (staging|ready|error),
staging {release, done_bytes, total_bytes, files_done, files_total},
blast_version, running, waiting, searches, timeouts, failures, error,
abandoned, killed, processes, batches, batched, batch_mean, batch_max,
batch_wait_s, batch_spread, slots}.
POST /search {release, query, task, max_target_seqs, timeout_s}: 200
{release, seconds, output: <-outfmt 15 report>}; 409 not ready or another
release; 422 bad request; 504 out of time; 500 BLAST failed.

2026-11-23: batches, and clients that leave. nt (1.1 TB) does not fit in the
page cache, so every blastn search read the whole NVMe copy: 4 slots ran
~8 searches an hour while 46 waited. Searches with the same release, task
and max_target_seqs that wait together now run as one BLAST process with a
multi-query FASTA (one read of the database for all), and each gets the
report a search of its own would have returned (checked on small protein and
nucleotide databases with BLAST 2.17: same hits, order, scores, statistics;
only query_id Query_<n> is renamed back to Query_1). A query BLAST rejects
or cannot score (a message other than "No hits found") is searched again on
its own, so it gets BLAST's own answer (these return at once, without
reading the database). A waiting or running search whose client closed the
connection (its worker run was cancelled, or it gave up) is dropped and
counted as abandoned; a BLAST process nobody waits for any more is killed.
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
POLL_S = 2.0  # 2026-11-23: how often a waiting/running search checks its client
NO_HITS = "No hits found"


class _Search:
    """One POST /search while it waits, runs and is answered (2026-11-23)."""

    def __init__(self, release: str, query: str, task: Optional[str], max_targets: int,
                 deadline: float, gone: Optional[Callable[[], bool]]) -> None:
        self.release, self.query, self.task, self.max_targets = release, query, task, max_targets
        self.deadline = deadline
        self.gone = gone
        self.arrived = time.time()
        # same release, task and -max_target_seqs: one BLAST command line; a
        # query without letters ("---") fails a whole multi-query run: alone
        self.key: tuple = (release, task, max_targets) if re.search("[A-Za-z]", query) else (id(self),)
        self.state = "waiting"  # running, done
        self.result: tuple[int, dict[str, Any]] = (500, {"error": "no answer"})
        self.done = threading.Event()

    def client_gone(self) -> bool:
        try:
            return bool(self.gone and self.gone())
        except Exception:
            return False


class Service:
    def __init__(self, db_path: str, local_dir: str, threads: int = 8, slots: int = 1,
                 stage_mbps: float = 40.0, snapshot: Optional[str] = None, streams: int = 8,
                 batch_max: int = 1, batch_wait_s: float = 0.0, batch_spread: str = "auto") -> None:
        from .blastdb_fetch import release_name
        self.db_path = db_path
        self.db_name = os.path.basename(db_path)
        self.local = Path(local_dir)
        self.threads = threads
        self.stage_bps = stage_mbps * 1e6
        self.lock = threading.RLock()  # 2026-11-23: also self.cv's lock; _finish under _take
        # 2026-11-23: waiting searches, taken in batches by up to `slots`
        # runner threads (was a semaphore per search)
        self.slots = max(1, slots)
        self.batch_max = max(1, batch_max)
        self.batch_wait_s = max(0.0, batch_wait_s)
        self.batch_spread = batch_spread
        self.cv = threading.Condition(self.lock)
        self.pending: list[_Search] = []
        self.runners = 0          # runner threads
        self.busy = 0             # runner threads with a batch (slots in use)
        self._spread: dict[str, bool] = {}
        self.release: Optional[str] = None
        # AWS snapshot to download ahead of the NFS switch (blastdb_fetch)
        self.snapshot = snapshot
        self.prefetch = release_name(self.db_name, snapshot) if snapshot else None
        self.streams = streams
        self.staging: dict[str, Any] = {}
        self.error = ""
        self.counts = {"running": 0, "waiting": 0, "searches": 0, "timeouts": 0, "failures": 0,
                       # 2026-11-23: clients that left, BLAST processes killed for
                       # them, processes running, processes run and their searches
                       "abandoned": 0, "killed": 0, "processes": 0, "batches": 0, "batched": 0,
                       "deduplicated": 0}
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
                    "slots": self.slots, "batch_max": self.batch_max, "batch_wait_s": self.batch_wait_s,
                    "batch_spread": bool(self.release and self.batch_max > 1 and self._spreads(self.release)),
                    "batch_mean": round(self.counts["batched"] / self.counts["batches"], 2)
                    if self.counts["batches"] else None,
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
        """Answer one search. `gone` tells whether the client closed the
        connection (2026-11-23): then the search is dropped and 499 returned
        (nothing is sent)."""
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
        # 2026-11-23: queue the search for the runner threads; check the
        # client and the deadline every POLL_S while it waits and runs
        s = _Search(release, query, task, max_targets, time.time() + timeout_s, gone)
        with self.cv:
            self.pending.append(s)
            self.counts["waiting"] += 1
            self._start_runners()
            self.cv.notify_all()
        while not s.done.wait(max(0.0, min(POLL_S, s.deadline - time.time()))):
            if s.client_gone():
                self._finish(s, 499, {"error": "client closed the connection"}, "abandoned")
            elif time.time() >= s.deadline:
                self._finish(s, 504, {"error": "timed out waiting for a free slot" if s.state == "waiting"
                                      else "BLAST ran out of time"}, "timeouts")
        return s.result

    # -- 2026-11-23: batches ----------------------------------------------------

    def _finish(self, s: _Search, code: int, body: dict[str, Any], count: Optional[str]) -> None:
        """Answer a search once (the first answer wins)."""
        with self.cv:
            if s.state == "done":
                return
            if s.state == "waiting":
                self.pending.remove(s)
                self.counts["waiting"] -= 1
            else:
                self.counts["running"] -= 1
            s.state, s.result = "done", (code, body)
            if count:
                self.counts[count] += 1
            s.done.set()
            self.cv.notify_all()

    def _start_runners(self) -> None:
        """A runner thread for waiting searches while a slot is free and no
        runner is free to take them (under self.cv)."""
        while self.pending and self.runners == self.busy and self.runners < self.slots:
            self.runners += 1
            threading.Thread(target=self._runner, daemon=True, name="blast-runner").start()

    def _runner(self) -> None:
        while True:
            with self.cv:
                batch = self._take()
                if not batch:
                    self.runners -= 1
                    return
                self.busy += 1
                self._start_runners()
            try:
                self._run_batch(batch)
            finally:
                with self.cv:
                    self.busy -= 1

    def _take(self) -> list[_Search]:
        """The next batch: the oldest waiting search and those waiting with
        the same key (under self.cv). A search on an idle service waits up to
        batch_wait_s from its arrival for others to join; one that already
        waited for a slot does not wait again."""
        while True:
            for s in [s for s in self.pending if s.client_gone()]:
                self._finish(s, 499, {"error": "client closed the connection"}, "abandoned")
            if not self.pending:
                return []
            head = self.pending[0]
            same = [s for s in self.pending if s.key == head.key]
            left = head.arrived + self.batch_wait_s - time.time()
            if self.batch_max == 1 or len(same) >= self.batch_max or left <= 0:
                break
            self.cv.wait(min(left, POLL_S))
        take = min(self.batch_max, len(same))
        if self._spreads(head.release):
            # the database is in the page cache: searches are CPU-bound, so
            # waiting searches go to all free slots rather than one batch
            take = min(take, -(-len(same) // max(1, self.slots - self.busy)))
        batch = same[:take]
        for s in batch:
            self.pending.remove(s)
            s.state = "running"
        self.counts["waiting"] -= len(batch)
        self.counts["running"] += len(batch)
        return batch

    def _spreads(self, release: str) -> bool:
        if self.batch_spread in ("0", "1"):
            return self.batch_spread == "1"
        if release not in self._spread:
            try:
                size = sum(p.stat().st_size for p in (self.local / release).iterdir() if p.is_file())
            except OSError:
                return False
            self._spread[release] = size < _memory_limit()
        return self._spread[release]

    def _run_batch(self, batch: list[_Search]) -> None:
        # 2026-11-23: identical queries (copies of one molecule in different
        # runs) are searched once; every one of them gets that answer
        unique: list[_Search] = []
        index: dict[str, int] = {}
        for s in batch:
            if s.query not in index:
                index[s.query] = len(unique)
                unique.append(s)
        if len(unique) < len(batch):
            with self.cv:
                self.counts["deduplicated"] += len(batch) - len(unique)
        try:
            answers = self._run(batch[0].release, unique, members=batch)
        except Exception as exc:
            log.exception("BLAST batch of %d failed", len(unique))
            answers = [(500, {"error": f"BLAST service: {exc}"})] * len(unique)
        alone: dict[int, list[_Search]] = {}
        for s in batch:
            answer = answers[index[s.query]]
            if answer is None:
                alone.setdefault(index[s.query], []).append(s)
            else:
                self._finish(s, *answer, _COUNT.get(answer[0]))
        for i, group in alone.items():
            # BLAST rejected or could not score this query in the batch: its
            # own answer (an error, or a message worded differently)
            waiting = [s for s in group if s.state == "running"]
            if waiting:
                answer = self._run(waiting[0].release, [unique[i]], members=waiting)[0] \
                    or (500, {"error": "no answer"})
                for s in waiting:
                    self._finish(s, *answer, _COUNT.get(answer[0]))

    def _run(self, release: str, batch: list[_Search],
             members: Optional[list[_Search]] = None) -> list[Optional[tuple[int, dict[str, Any]]]]:
        """Run one BLAST process for the batch: an answer per search, or None
        for a search to run again on its own. One search: its query on stdin,
        as before 2026-11-23; more: a FASTA with empty deflines (BLAST then
        names and titles each query as it does a lone one, Query_<n>).
        `members` are all the searches waiting on these queries (duplicates
        included): BLAST runs while any of them waits, up to their latest
        deadline."""
        members = members or batch
        tmp = tempfile.mkdtemp(prefix="blast-")
        out, err = os.path.join(tmp, "out.json"), os.path.join(tmp, "stderr")
        with open(os.path.join(tmp, "query"), "w") as f:
            f.write(batch[0].query if len(batch) == 1 else "".join(f">\n{s.query}\n" for s in batch))
        first = batch[0]
        cmd = [self.program, "-outfmt", "15", "-db", str(self.local / release / self.db_name),
               "-out", out, "-num_threads", str(self.threads), "-max_target_seqs", str(first.max_targets)]
        if first.task:
            cmd += ["-task", first.task]
        env = None
        if len(batch) > 1 and "BATCH_SIZE" not in os.environ:
            # all queries in one pass over the database (BLAST's default
            # batch is 10,000 residues for blastp); results do not change
            env = {**os.environ, "BATCH_SIZE": str(sum(len(s.query) + 1 for s in batch))}
        with self.cv:
            self.counts["processes"] += 1
            self.counts["batches"] += 1
            self.counts["batched"] += len(batch)
        started = time.time()
        deadline = max(s.deadline for s in members)
        try:
            with open(os.path.join(tmp, "query")) as qf, open(err, "w") as ef:
                proc = subprocess.Popen(cmd, stdin=qf, stdout=subprocess.DEVNULL, stderr=ef, env=env)
            try:
                while True:
                    try:
                        rc = proc.wait(timeout=max(0.1, min(POLL_S / 2, deadline - time.time())))
                        break
                    except subprocess.TimeoutExpired:
                        with self.cv:
                            wanted = any(s.state == "running" for s in members)
                        if not wanted or time.time() >= deadline:
                            proc.kill()
                            proc.wait()
                            if not wanted:
                                with self.cv:
                                    self.counts["killed"] += 1
                                log.info("killed BLAST for %d searches: their clients left", len(batch))
                            return [(504, {"error": "BLAST ran out of time"})] * len(batch)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                with self.cv:
                    self.counts["processes"] -= 1
            if rc != 0:
                with open(err) as f:
                    stderr = f.read()
                return [(500, {"error": f"BLAST exit {rc}: {stderr.strip()[:500]}"})] * len(batch)
            with open(out) as f:
                report = json.load(f)
            seconds = round(time.time() - started, 1)
            if len(batch) > 1:
                log.info("batch of %d searches (%s, max_target_seqs %d): %.0f s",
                         len(batch), first.task or self.program, first.max_targets, seconds)
            if len(batch) == 1:
                return [(200, {"release": release, "seconds": seconds, "output": report})]
            return [None if rep is None else (200, {"release": release, "seconds": seconds, "output": rep})
                    for rep in _split(report, len(batch))]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


_COUNT = {200: "searches", 500: "failures", 504: "timeouts"}


def _split(report: dict[str, Any], n: int) -> list[Optional[dict[str, Any]]]:
    """A multi-query -outfmt 15 report as n single-query reports, each as
    BLAST writes it for that query alone; None for a query BLAST could not
    search (a message other than "No hits found": run it alone)."""
    reports = report.get("BlastOutput2")
    if not isinstance(reports, list) or len(reports) != n:
        raise ValueError(f"{len(reports) if isinstance(reports, list) else 'no'} reports for {n} queries")
    out: list[Optional[dict[str, Any]]] = []
    for i, rep in enumerate(reports):
        search = rep["report"]["results"]["search"]
        if search.get("query_id") != f"Query_{i + 1}":
            raise ValueError(f"report {i + 1} is for {search.get('query_id')}")
        if search.get("message", NO_HITS) != NO_HITS:
            out.append(None)
            continue
        search["query_id"] = "Query_1"
        out.append(dict(report, BlastOutput2=[rep]))
    return out


def _memory_limit() -> int:
    """The pod's memory limit (cgroup), else the machine's memory."""
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            value = Path(path).read_text().strip()
            if value.isdigit() and int(value) < 1 << 60:
                return int(value)
        except OSError:
            pass
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        return 0


def make_handler(service: Service) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            super().setup()
            # 2026-11-23: a worker whose pod vanished sends no FIN; keepalive
            # probes find the dead connection within ~2 min (Linux)
            try:
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                for opt, value in (("TCP_KEEPIDLE", 60), ("TCP_KEEPINTVL", 10), ("TCP_KEEPCNT", 6)):
                    if hasattr(socket, opt):
                        self.connection.setsockopt(socket.IPPROTO_TCP, getattr(socket, opt), value)
            except OSError:
                pass

        def _send(self, code: int, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _client_gone(self) -> bool:
            """The client closed the connection (2026-11-23): the socket reads
            as finished, or reports a hang-up or error."""
            p = select.poll()
            p.register(self.connection, select.POLLIN | select.POLLHUP | select.POLLERR)
            for _, ev in p.poll(0):
                if ev & (select.POLLHUP | select.POLLERR):
                    return True
                if ev & select.POLLIN:
                    try:
                        return self.connection.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT) == b""
                    except BlockingIOError:
                        return False
                    except OSError:
                        return True
            return False

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
            code, body = service.search(req if isinstance(req, dict) else {}, gone=self._client_gone)
            if code == 499:  # 2026-11-23: the client left; nobody to answer
                self.close_connection = True
                return
            try:
                self._send(code, body)
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
                with service.lock:
                    service.counts["abandoned"] += 1

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
        batch_max=int(os.environ.get("BLAST_BATCH_MAX", "16")),
        batch_wait_s=float(os.environ.get("BLAST_BATCH_WAIT_S", "2")),
        batch_spread=os.environ.get("BLAST_BATCH_SPREAD", "auto"),
    )
    threading.Thread(target=service.keep_current, daemon=True, name="stage").start()
    server = ThreadingHTTPServer(("", int(os.environ.get("PORT", "8080"))), make_handler(service))
    log.info("%s: %s, release %s", service.db_name, service.state(), service.release)
    server.serve_forever()


if __name__ == "__main__":
    main()
